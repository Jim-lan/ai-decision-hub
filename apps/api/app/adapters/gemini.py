"""Fail-closed Gemini Developer API adapter for the frozen ProviderPort."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from math import ceil
from time import monotonic
from typing import Callable, Literal, Protocol

import httpx
from google import genai
from google.genai import errors, types

from app.ports import (
    AuthorizationPort,
    CostEstimate,
    DispatchGrant,
    FailureCode,
    GenerationRequest,
    GenerationResult,
    ModelCapabilities,
    ProviderPort,
)


@dataclass(frozen=True)
class GeminiQualification:
    """Owner-reviewed facts required before this adapter may send a request."""

    enabled: bool
    project_id: str | None
    tier: Literal["paid"] | None
    region: str | None
    requested_model_id: str | None
    accepted_model_ids: tuple[str, ...]
    model_family: str | None
    max_input_tokens: int | None
    max_output_tokens: int | None
    input_microusd_per_million: int | None
    output_microusd_per_million: int | None
    verified_at: datetime | None
    expires_at: datetime | None
    data_terms: Literal["paid-no-training"] | None

    def is_current(self, now: datetime) -> bool:
        verified_at = self.verified_at
        expires_at = self.expires_at
        max_input = self.max_input_tokens
        max_output = self.max_output_tokens
        input_price = self.input_microusd_per_million
        output_price = self.output_microusd_per_million
        if (
            not self.enabled
            or not self.project_id
            or not self.region
            or not self.requested_model_id
            or not self.model_family
            or verified_at is None
            or expires_at is None
            or max_input is None
            or max_output is None
            or input_price is None
            or output_price is None
            or now.tzinfo is None
            or verified_at.tzinfo is None
            or expires_at.tzinfo is None
        ):
            return False
        return (
            bool(self.accepted_model_ids)
            and len(set(self.accepted_model_ids)) == len(self.accepted_model_ids)
            and all(model.strip() == model and model for model in self.accepted_model_ids)
            and self.project_id.strip() == self.project_id
            and self.region.strip() == self.region
            and self.requested_model_id.strip() == self.requested_model_id
            and self.model_family.strip() == self.model_family
            and self.requested_model_id in self.accepted_model_ids
            and self.tier == "paid"
            and self.data_terms == "paid-no-training"
            and verified_at <= now < expires_at
            and max_input > 0
            and max_output > 0
            and input_price >= 0
            and output_price >= 0
        )


@dataclass(frozen=True)
class GeminiResponse:
    text: str | None
    model_version: str | None
    prompt_token_count: int | None
    candidates_token_count: int | None
    thoughts_token_count: int | None = None


class GeminiTransportFailure(Exception):
    """Sanitized transport failure; never contains a credential or response body."""

    def __init__(self, *, status_code: int | None = None, timed_out: bool = False):
        super().__init__("Gemini transport failed")
        self.status_code = status_code
        self.timed_out = timed_out


class GeminiTransport(Protocol):
    async def generate(
        self,
        *,
        model_id: str,
        prompt: str,
        max_output_tokens: int,
        timeout_ms: int,
    ) -> GeminiResponse: ...


class GoogleGenAITransport:
    """Official stable-v1 SDK transport with retries explicitly disabled."""

    base_url = "https://generativelanguage.googleapis.com"

    def __init__(
        self,
        api_key: str,
        *,
        _async_transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key.strip():
            raise ValueError("Gemini API key is required")
        self._api_key = api_key
        self._async_transport = _async_transport

    async def generate(
        self,
        *,
        model_id: str,
        prompt: str,
        max_output_tokens: int,
        timeout_ms: int,
    ) -> GeminiResponse:
        try:
            with httpx.Client(follow_redirects=False, trust_env=False) as sync_http:
                async with httpx.AsyncClient(
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._async_transport,
                ) as async_http:
                    options = types.HttpOptions(
                        api_version="v1",
                        base_url=self.base_url,
                        timeout=timeout_ms,
                        retry_options=types.HttpRetryOptions(attempts=1),
                        httpx_client=sync_http,
                        httpx_async_client=async_http,
                    )
                    client = genai.Client(
                        enterprise=False,
                        vertexai=False,
                        api_key=self._api_key,
                        http_options=options,
                    )
                    async with client.aio as async_client:
                        response = await async_client.models.generate_content(
                            model=model_id,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                candidate_count=1,
                                max_output_tokens=max_output_tokens,
                                automatic_continuation=False,
                                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                                    disable=True,
                                ),
                                store=False,
                            ),
                        )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise GeminiTransportFailure(timed_out=True) from exc
        except errors.APIError as exc:
            raise GeminiTransportFailure(status_code=exc.code) from exc
        except Exception as exc:
            raise GeminiTransportFailure() from exc

        usage = getattr(response, "usage_metadata", None)
        try:
            text = response.text
        except (AttributeError, ValueError):
            text = None
        return GeminiResponse(
            text=text,
            model_version=getattr(response, "model_version", None),
            prompt_token_count=getattr(usage, "prompt_token_count", None),
            candidates_token_count=getattr(usage, "candidates_token_count", None),
            thoughts_token_count=getattr(usage, "thoughts_token_count", None),
        )


class GeminiProvider(ProviderPort):
    """ProviderPort mapping that refuses calls without durable authorization.

    The transaction callbacks must belong to the dedicated C-010 claim transaction.
    A successful claim is committed before transport. The receipt observer receives
    every returned payload before identity validation so C-009 can preserve raw
    evidence without expanding the transport-neutral ProviderPort contract.
    """

    provider_id = "google"

    def __init__(
        self,
        transport: GeminiTransport,
        qualification: GeminiQualification,
        authorization: AuthorizationPort,
        commit_claim: Callable[[], None],
        rollback_claim: Callable[[], None],
        receipt_observer: Callable[[GenerationRequest, GeminiResponse], None],
    ):
        self._transport = transport
        self._qualification = qualification
        self._authorization = authorization
        self._commit_claim = commit_claim
        self._rollback_claim = rollback_claim
        self._receipt_observer = receipt_observer

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _input_bound(text: str) -> int:
        # A UTF-8 byte is a conservative token upper bound for nonempty text.
        return len(text.encode("utf-8"))

    @staticmethod
    def _valid_measured_tokens(value: int | None) -> bool:
        return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)

    def _failure(
        self,
        request: GenerationRequest,
        error_code: FailureCode,
        elapsed_ms: int = 0,
        *,
        actual_model_id: str | None = None,
    ) -> GenerationResult:
        return GenerationResult(
            status="failed",
            requested_model_id=request.requested_model_id,
            actual_model_id=actual_model_id,
            model_family=None,
            content=None,
            elapsed_ms=elapsed_ms,
            input_tokens=None,
            output_tokens=None,
            error_code=error_code,
        )

    def _preflight_error(self, request: GenerationRequest) -> FailureCode | None:
        profile = self._qualification
        if not profile.is_current(self._now()):
            return "disabled"
        if request.provider_id != self.provider_id:
            return "policy_denied"
        if request.requested_model_id != profile.requested_model_id:
            return "policy_denied"
        if request.requested_model_id not in request.allowed_model_ids:
            return "policy_denied"
        if request.requested_model_id not in profile.accepted_model_ids:
            return "policy_denied"
        if request.timeout_ms <= 0 or request.max_output_tokens <= 0:
            return "invalid_response"
        assert profile.max_output_tokens is not None
        assert profile.max_input_tokens is not None
        if request.max_output_tokens > profile.max_output_tokens:
            return "budget_denied"
        if self._input_bound(request.model_visible_input) > profile.max_input_tokens:
            return "quota_denied"
        return None

    @staticmethod
    def _grant_matches(request: GenerationRequest, grant: DispatchGrant) -> bool:
        return (
            grant.grant_id == request.grant_id
            and grant.attempt_id == request.attempt_id
            and grant.provider_id == request.provider_id
            and grant.requested_model_id == request.requested_model_id
            and grant.input_digest
            == sha256(request.model_visible_input.encode("utf-8")).hexdigest()
            and grant.output_token_bound == request.max_output_tokens
        )

    def _claim_dispatch(self, request: GenerationRequest) -> bool:
        try:
            grant = self._authorization.validate_dispatch(request, self._now())
            if not self._grant_matches(request, grant):
                self._rollback_claim()
                return False
            self._commit_claim()
        except Exception:
            self._rollback_claim()
            return False
        return True

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        failure = self._preflight_error(request)
        if failure:
            return self._failure(request, failure)
        if not self._claim_dispatch(request):
            return self._failure(request, "policy_denied")
        if not self._qualification.is_current(self._now()):
            return self._failure(request, "disabled")

        started = monotonic()
        try:
            response = await self._transport.generate(
                model_id=request.requested_model_id,
                prompt=request.model_visible_input,
                max_output_tokens=request.max_output_tokens,
                timeout_ms=request.timeout_ms,
            )
        except GeminiTransportFailure as exc:
            elapsed = max(0, round((monotonic() - started) * 1000))
            return self._failure(request, self._map_transport_error(exc), elapsed)

        elapsed = max(0, round((monotonic() - started) * 1000))
        try:
            self._receipt_observer(request, response)
        except Exception:
            return self._failure(request, "internal_error", elapsed)
        actual_model = response.model_version
        if (
            not isinstance(response.text, str)
            or not response.text
            or not self._valid_measured_tokens(response.prompt_token_count)
            or not self._valid_measured_tokens(response.candidates_token_count)
            or not self._valid_measured_tokens(response.thoughts_token_count)
        ):
            return self._failure(
                request,
                "invalid_response",
                elapsed,
                actual_model_id=actual_model,
            )
        if actual_model is None:
            return GenerationResult(
                status="succeeded",
                requested_model_id=request.requested_model_id,
                actual_model_id=None,
                model_family=None,
                content=response.text,
                elapsed_ms=elapsed,
                input_tokens=response.prompt_token_count,
                output_tokens=self._output_tokens(response),
                error_code=None,
            )
        if (
            not isinstance(actual_model, str)
            or not actual_model
            or actual_model not in request.allowed_model_ids
            or actual_model not in self._qualification.accepted_model_ids
        ):
            return self._failure(
                request,
                "invalid_response",
                elapsed,
                actual_model_id=actual_model if isinstance(actual_model, str) else None,
            )
        return GenerationResult(
            status="succeeded",
            requested_model_id=request.requested_model_id,
            actual_model_id=actual_model,
            model_family=self._qualification.model_family,
            content=response.text,
            elapsed_ms=elapsed,
            input_tokens=response.prompt_token_count,
            output_tokens=self._output_tokens(response),
            error_code=None,
        )

    @staticmethod
    def _output_tokens(response: GeminiResponse) -> int | None:
        if response.candidates_token_count is None or response.thoughts_token_count is None:
            return None
        return response.candidates_token_count + response.thoughts_token_count

    @staticmethod
    def _map_transport_error(exc: GeminiTransportFailure) -> FailureCode:
        if exc.timed_out or exc.status_code in (408, 504):
            return "timeout"
        if exc.status_code == 429:
            return "quota_denied"
        if exc.status_code == 499:
            return "cancelled"
        if exc.status_code in (401, 403):
            return "policy_denied"
        if exc.status_code is None:
            return "delivery_unknown"
        return "provider_error"

    async def capabilities(self, model_id: str) -> ModelCapabilities:
        profile = self._qualification
        if not profile.is_current(self._now()) or model_id != profile.requested_model_id:
            raise PermissionError("Gemini model is not currently qualified")
        assert profile.max_input_tokens is not None
        assert profile.max_output_tokens is not None
        assert profile.verified_at is not None
        return ModelCapabilities(
            model_id=model_id,
            max_input_tokens=profile.max_input_tokens,
            max_output_tokens=profile.max_output_tokens,
            verified_at=profile.verified_at,
        )

    async def estimate_cost(self, request: GenerationRequest) -> CostEstimate:
        failure = self._preflight_error(request)
        if failure:
            raise PermissionError(f"Gemini request is not qualified: {failure}")
        profile = self._qualification
        assert profile.input_microusd_per_million is not None
        assert profile.output_microusd_per_million is not None
        assert profile.verified_at is not None
        input_bound = self._input_bound(request.model_visible_input)
        input_cost = ceil(
            input_bound * profile.input_microusd_per_million / 1_000_000
        )
        output_cost = ceil(
            request.max_output_tokens
            * profile.output_microusd_per_million
            / 1_000_000
        )
        return CostEstimate(
            amount_microusd=input_cost + output_cost,
            input_token_bound=input_bound,
            output_token_bound=request.max_output_tokens,
            price_verified_at=profile.verified_at,
        )
