import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.adapters.gemini import (
    GeminiProvider,
    GeminiQualification,
    GeminiResponse,
    GeminiTransportFailure,
    GoogleGenAITransport,
)
from app.ports import DispatchGrant, GenerationRequest, ProviderPort


NOW = datetime(2026, 11, 13, 19, 41, tzinfo=timezone.utc)
MODEL = "gemini-qualified-model"


class RecordingTransport:
    def __init__(self, response=None, failure=None, events=None):
        self.response = response
        self.failure = failure
        self.calls = []
        self.events = events

    async def generate(self, **kwargs):
        if self.events is not None:
            self.events.append("transport")
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return self.response


def qualification(*, enabled=True, expires_at=None):
    return GeminiQualification(
        enabled=enabled,
        project_id="synthetic-test-project",
        tier="paid",
        region="CA",
        requested_model_id=MODEL,
        accepted_model_ids=(MODEL,),
        model_family="Gemini qualified family",
        max_input_tokens=4096,
        max_output_tokens=1024,
        input_microusd_per_million=1_000_000,
        output_microusd_per_million=4_000_000,
        verified_at=NOW - timedelta(days=1),
        expires_at=expires_at or NOW + timedelta(days=1),
        data_terms="paid-no-training",
    )


def request(**changes):
    values = {
        "attempt_id": uuid4(),
        "grant_id": uuid4(),
        "provider_id": "google",
        "requested_model_id": MODEL,
        "model_visible_input": "Non-sensitive deterministic prompt",
        "timeout_ms": 1500,
        "max_output_tokens": 64,
        "allowed_model_ids": (MODEL,),
    }
    values.update(changes)
    return GenerationRequest(**values)


class FakeAuthorization:
    def __init__(
        self,
        *,
        deny=False,
        mutate=None,
        one_shot=False,
        events=None,
        on_validate=None,
    ):
        self.deny = deny
        self.mutate = mutate
        self.one_shot = one_shot
        self.events = events
        self.claimed = False
        self.on_validate = on_validate

    def validate_dispatch(self, generation, as_of):
        if self.events is not None:
            self.events.append("authorize")
        if self.deny or (self.one_shot and self.claimed):
            raise PermissionError("Synthetic grant denied")
        if self.on_validate:
            self.on_validate()
        self.claimed = True
        grant = DispatchGrant(
            grant_id=generation.grant_id,
            reservation_id=uuid4(),
            candidate_id=uuid4(),
            attempt_id=generation.attempt_id,
            owner_id=uuid4(),
            project_id=uuid4(),
            run_id=uuid4(),
            target_id=uuid4(),
            provider_id=generation.provider_id,
            alias="gemini-api-candidate",
            requested_model_id=generation.requested_model_id,
            input_digest=sha256(generation.model_visible_input.encode("utf-8")).hexdigest(),
            input_token_bound=len(generation.model_visible_input.encode("utf-8")),
            output_token_bound=generation.max_output_tokens,
            deadline=as_of + timedelta(minutes=1),
            validated_at=as_of,
        )
        return self.mutate(grant) if self.mutate else grant


def adapter(
    transport,
    profile=None,
    authorization=None,
    events=None,
    commit_failure=False,
    clock=None,
    observer=None,
):
    authorization = authorization or FakeAuthorization(events=events)

    def commit():
        if events is not None:
            events.append("commit")
        if commit_failure:
            raise RuntimeError("Synthetic commit failure")

    def rollback():
        if events is not None:
            events.append("rollback")

    receipts = []

    def observe(generation, response):
        receipts.append((generation, response))

    provider = GeminiProvider(
        transport,
        profile or qualification(),
        authorization,
        commit,
        rollback,
        observer or observe,
    )
    provider._now = clock or (lambda: NOW)
    provider.receipts = receipts
    return provider


def test_disabled_or_expired_qualification_never_touches_transport():
    for profile in (
        qualification(enabled=False),
        qualification(expires_at=NOW),
    ):
        transport = RecordingTransport()
        provider = adapter(transport, profile)
        result = asyncio.run(provider.generate(request()))
        assert result.status == "failed"
        assert result.error_code == "disabled"
        assert transport.calls == []
        with pytest.raises(PermissionError, match="not currently qualified"):
            asyncio.run(provider.capabilities(MODEL))
        with pytest.raises(PermissionError, match="disabled"):
            asyncio.run(provider.estimate_cost(request()))


def test_success_maps_official_identity_content_and_usage_without_sdk_types_crossing_port():
    events = []
    transport = RecordingTransport(
        GeminiResponse(
            text="Synthetic Gemini answer",
            model_version=MODEL,
            prompt_token_count=7,
            candidates_token_count=11,
            thoughts_token_count=2,
        ),
        events=events,
    )
    provider = adapter(transport, events=events)
    assert isinstance(provider, ProviderPort)
    result = asyncio.run(provider.generate(request()))
    assert result.status == "succeeded"
    assert result.requested_model_id == result.actual_model_id == MODEL
    assert result.model_family == "Gemini qualified family"
    assert result.content == "Synthetic Gemini answer"
    assert (result.input_tokens, result.output_tokens) == (7, 13)
    assert result.error_code is None
    assert transport.calls == [
        {
            "model_id": MODEL,
            "prompt": "Non-sensitive deterministic prompt",
            "max_output_tokens": 64,
            "timeout_ms": 1500,
        }
    ]
    assert events == ["authorize", "commit", "transport"]
    assert len(provider.receipts) == 1
    assert provider.receipts[0][1] == transport.response


def test_estimate_is_conservative_and_capabilities_are_profile_bound():
    provider = adapter(RecordingTransport())
    capabilities = asyncio.run(provider.capabilities(MODEL))
    assert capabilities.model_id == MODEL
    assert capabilities.max_input_tokens == 4096
    assert capabilities.max_output_tokens == 1024
    estimate = asyncio.run(provider.estimate_cost(request(model_visible_input="é", max_output_tokens=2)))
    assert estimate.input_token_bound == 2
    assert estimate.output_token_bound == 2
    assert estimate.amount_microusd == 10


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (GeminiTransportFailure(timed_out=True), "timeout"),
        (GeminiTransportFailure(status_code=429), "quota_denied"),
        (GeminiTransportFailure(status_code=499), "cancelled"),
        (GeminiTransportFailure(status_code=403), "policy_denied"),
        (GeminiTransportFailure(status_code=503), "provider_error"),
        (GeminiTransportFailure(), "delivery_unknown"),
    ],
)
def test_transport_failures_are_sanitized_and_classified_without_retry(failure, expected):
    transport = RecordingTransport(failure=failure)
    result = asyncio.run(adapter(transport).generate(request()))
    assert result.status == "failed"
    assert result.error_code == expected
    assert result.content is None
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"provider_id": "other"},
        {"requested_model_id": "unqualified"},
        {"allowed_model_ids": ("other",)},
        {"max_output_tokens": 1025},
        {"model_visible_input": "x" * 4097},
        {"timeout_ms": 0},
    ],
)
def test_failed_preflight_never_touches_transport(changes):
    transport = RecordingTransport()
    result = asyncio.run(adapter(transport).generate(request(**changes)))
    assert result.status == "failed"
    assert transport.calls == []


def test_denied_mismatched_or_uncommitted_grant_never_touches_transport():
    cases = (
        {"authorization": FakeAuthorization(deny=True)},
        {"authorization": FakeAuthorization(mutate=lambda grant: replace(grant, grant_id=uuid4()))},
        {"commit_failure": True},
    )
    for case in cases:
        events = []
        transport = RecordingTransport(events=events)
        provider = adapter(transport, events=events, **case)
        result = asyncio.run(provider.generate(request()))
        assert result.status == "failed"
        assert result.error_code == "policy_denied"
        assert transport.calls == []
        assert "rollback" in events
        assert "transport" not in events


def test_one_shot_authorization_blocks_replay_after_committed_claim():
    authorization = FakeAuthorization(one_shot=True)
    transport = RecordingTransport(GeminiResponse("answer", MODEL, 1, 1, 0))
    provider = adapter(transport, authorization=authorization)
    generation = request()
    assert asyncio.run(provider.generate(generation)).status == "succeeded"
    replay = asyncio.run(provider.generate(generation))
    assert replay.status == "failed"
    assert replay.error_code == "policy_denied"
    assert len(transport.calls) == 1


def test_qualification_expiry_during_claim_commits_hold_but_sends_nothing():
    current = [NOW]
    expiry = NOW + timedelta(seconds=1)
    events = []
    authorization = FakeAuthorization(
        events=events,
        on_validate=lambda: current.__setitem__(0, expiry),
    )
    transport = RecordingTransport(events=events)
    provider = adapter(
        transport,
        profile=qualification(expires_at=expiry),
        authorization=authorization,
        events=events,
        clock=lambda: current[0],
    )
    result = asyncio.run(provider.generate(request()))
    assert result.status == "failed"
    assert result.error_code == "disabled"
    assert authorization.claimed is True
    assert events == ["authorize", "commit"]
    assert transport.calls == []


def test_raw_receipt_observer_failure_does_not_retry_transport():
    transport = RecordingTransport(GeminiResponse("answer", MODEL, 1, 1, 0))

    def fail_observer(*_):
        raise RuntimeError("Synthetic receipt persistence failure")

    result = asyncio.run(adapter(transport, observer=fail_observer).generate(request()))
    assert result.status == "failed"
    assert result.error_code == "internal_error"
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        GeminiResponse("answer", "unexpected-model", 1, 1),
        GeminiResponse(None, MODEL, 1, 1),
        GeminiResponse("", MODEL, 1, 1),
        GeminiResponse("answer", MODEL, -1, 1),
        GeminiResponse("answer", MODEL, 1, -1),
        GeminiResponse("answer", MODEL, 1, 1, -1),
    ],
)
def test_untraceable_or_empty_success_is_rejected(response):
    provider = adapter(RecordingTransport(response))
    result = asyncio.run(provider.generate(request()))
    assert result.status == "failed"
    assert result.error_code == "invalid_response"
    assert result.content is None
    assert len(provider.receipts) == 1
    assert provider.receipts[0][1] == response


def test_missing_returned_identity_preserves_original_with_unknown_provenance():
    response = GeminiResponse("answer", None, 1, 2, 0)
    result = asyncio.run(adapter(RecordingTransport(response)).generate(request()))
    assert result.status == "succeeded"
    assert result.content == "answer"
    assert result.actual_model_id is None
    assert result.model_family is None
    assert result.output_tokens == 2


def test_unknown_usage_remains_unknown_instead_of_becoming_zero():
    response = GeminiResponse("answer", MODEL, None, None, None)
    result = asyncio.run(adapter(RecordingTransport(response)).generate(request()))
    assert result.status == "succeeded"
    assert result.input_tokens is None
    assert result.output_tokens is None


def test_official_sdk_transport_pins_endpoint_version_timeout_and_single_attempt(monkeypatch):
    captured = {}

    class FakeModels:
        async def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                text="official fixture",
                model_version=MODEL,
                usage_metadata=SimpleNamespace(
                    prompt_token_count=3,
                    candidates_token_count=4,
                    thoughts_token_count=2,
                ),
            )

    class FakeAsyncClient:
        models = FakeModels()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class FakeClient:
        aio = FakeAsyncClient()

    def fake_client(**kwargs):
        captured["client"] = kwargs
        return FakeClient()

    monkeypatch.setattr("app.adapters.gemini.genai.Client", fake_client)
    result = asyncio.run(
        GoogleGenAITransport("fixture-key").generate(
            model_id=MODEL,
            prompt="fixture prompt",
            max_output_tokens=9,
            timeout_ms=1234,
        )
    )
    options = captured["client"]["http_options"]
    assert captured["client"]["api_key"] == "fixture-key"
    assert captured["client"]["enterprise"] is False
    assert captured["client"]["vertexai"] is False
    assert options.api_version == "v1"
    assert options.base_url == "https://generativelanguage.googleapis.com"
    assert options.timeout == 1234
    assert options.retry_options.attempts == 1
    assert options.httpx_client.follow_redirects is False
    assert options.httpx_async_client.follow_redirects is False
    assert options.httpx_client._trust_env is False
    assert options.httpx_async_client._trust_env is False
    assert captured["request"]["model"] == MODEL
    assert captured["request"]["contents"] == "fixture prompt"
    assert captured["request"]["config"].candidate_count == 1
    assert captured["request"]["config"].max_output_tokens == 9
    assert captured["request"]["config"].automatic_continuation is False
    assert captured["request"]["config"].automatic_function_calling.disable is True
    assert captured["request"]["config"].store is False
    assert result == GeminiResponse("official fixture", MODEL, 3, 4, 2)


def test_official_sdk_transport_does_not_follow_cross_host_redirect_or_environment(monkeypatch):
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            307,
            headers={"Location": "https://redirect.invalid/capture"},
            request=request,
        )

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", "https://environment.invalid")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.invalid")
    transport = GoogleGenAITransport(
        "fixture-key",
        _async_transport=httpx.MockTransport(handler),
    )
    with pytest.raises(GeminiTransportFailure):
        asyncio.run(
            transport.generate(
                model_id=MODEL,
                prompt="redirect canary",
                max_output_tokens=9,
                timeout_ms=1234,
            )
        )
    assert len(requests) == 1
    assert requests[0].url.host == "generativelanguage.googleapis.com"
    assert requests[0].url.host != "redirect.invalid"
    assert requests[0].url.host != "environment.invalid"


def test_official_sdk_continuation_response_causes_exactly_one_http_request():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "partial"}]},
                        "finishReason": "CONTINUATION",
                        "continuationToken": "dG9rZW4=",
                    }
                ],
                "modelVersion": MODEL,
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 4,
                    "thoughtsTokenCount": 2,
                    "totalTokenCount": 9,
                },
            },
            request=request,
        )

    result = asyncio.run(
        GoogleGenAITransport(
            "fixture-key",
            _async_transport=httpx.MockTransport(handler),
        ).generate(
            model_id=MODEL,
            prompt="continuation canary",
            max_output_tokens=9,
            timeout_ms=1234,
        )
    )
    assert len(requests) == 1
    assert result == GeminiResponse("partial", MODEL, 3, 4, 2)
