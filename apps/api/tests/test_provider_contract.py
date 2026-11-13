import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from app.contracts import OriginalDetails, Provider
from app.identity import IdentityEvidence, verified_family_count
from app.ports import (
    GenerationRequest,
    GenerationResult,
    ModelCapabilities,
    ProviderPort,
)
from tests.typed_provider_fakes import MappingFixtureProvider, StaticFixtureProvider, require_provider


FIXTURES = Path(__file__).parent / "fixtures" / "providers"
CONTRACT_ROOT = Path(__file__).resolve().parent
for _ in range(3):
    CONTRACT_ROOT = CONTRACT_ROOT.parent
CONTRACT_CANDIDATES = (CONTRACT_ROOT / "contracts/provider-result.schema.json",)
VERIFIED_AT = datetime(2026, 11, 9, tzinfo=timezone.utc)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def load_contract() -> dict:
    for candidate in CONTRACT_CANDIDATES:
        if candidate.exists():
            return json.loads(candidate.read_text())
    raise AssertionError("Provider result contract is unavailable")


def as_result(data: dict) -> GenerationResult:
    return GenerationResult(**{key: value for key, value in data.items() if key != "schema_version"})


def capabilities() -> ModelCapabilities:
    return ModelCapabilities("fixture-model", 4096, 1024, VERIFIED_AT)


def request(model_id: str = "fixture-model") -> GenerationRequest:
    return GenerationRequest(
        attempt_id=uuid4(),
        grant_id=uuid4(),
        provider_id="fixture",
        requested_model_id=model_id,
        model_visible_input="Synthetic non-sensitive prompt",
        timeout_ms=1500,
        max_output_tokens=64,
        allowed_model_ids=(model_id,),
    )


def test_provider_result_fixtures_follow_the_frozen_contract():
    validator = Draft202012Validator(load_contract())
    for name in ("success.json", "unknown-success.json", "timeout.json", "identity-mismatch.json"):
        assert not list(validator.iter_errors(load_fixture(name))), name
    errors = list(validator.iter_errors(load_fixture("incompatible.json")))
    assert errors, "The intentionally incompatible fixture must fail contract validation"


def test_two_adapters_substitute_behind_the_same_provider_port():
    result = as_result(load_fixture("success.json"))
    static = StaticFixtureProvider(result, capabilities())
    mapped = MappingFixtureProvider({"fixture-model": result}, capabilities())
    assert isinstance(static, ProviderPort)
    assert isinstance(mapped, ProviderPort)
    first, second = asyncio.run(_generate_both(require_provider(static), require_provider(mapped), request()))
    assert first == second == result


async def _generate_both(
    first: ProviderPort, second: ProviderPort, generation: GenerationRequest
) -> tuple[GenerationResult, GenerationResult]:
    return await first.generate(generation), await second.generate(generation)


def test_timeout_and_identity_mismatch_are_reproducible():
    timeout = StaticFixtureProvider(as_result(load_fixture("timeout.json")), capabilities())
    generation = request()
    assert asyncio.run(timeout.generate(generation)) == asyncio.run(timeout.generate(generation))
    assert asyncio.run(timeout.generate(generation)).error_code == "timeout"

    raw_mismatch = as_result(load_fixture("identity-mismatch.json"))
    mismatch_provider = StaticFixtureProvider(raw_mismatch, capabilities())
    mismatch = asyncio.run(mismatch_provider.generate(generation))
    assert mismatch == asyncio.run(mismatch_provider.generate(generation))
    assert raw_mismatch.status == "succeeded"
    assert mismatch.status == "failed"
    assert mismatch.error_code == "invalid_response"
    assert mismatch.actual_model_id != mismatch.requested_model_id


def test_success_preserves_unknown_identity_and_usage():
    raw = as_result(load_fixture("unknown-success.json"))
    result = asyncio.run(StaticFixtureProvider(raw, capabilities()).generate(request()))
    assert result == raw
    assert result.actual_model_id is result.model_family is None
    assert result.input_tokens is result.output_tokens is None


def test_verified_family_count_deduplicates_aliases_and_rejects_unattested_identity():
    confirmed = {
        "resolved_provider_id": "fixture-provider",
        "resolved_model_id": "fixture-model-2026-11",
        "model_family": "Fixture Family",
        "identity_confidence": "provider_reported",
        "acquisition_mode": "official_api",
    }
    identities = [
        IdentityEvidence(requested_alias="alias-a", **confirmed),
        IdentityEvidence(requested_alias="alias-b", **confirmed),
        IdentityEvidence(
            requested_alias="manual-label", resolved_provider_id=None,
            resolved_model_id=None, model_family="Fixture Family",
            identity_confidence="user_declared", acquisition_mode="manual",
        ),
        IdentityEvidence(
            requested_alias="dynamic-router", resolved_provider_id=None,
            resolved_model_id=None, model_family="unknown",
            identity_confidence="unknown", acquisition_mode="official_api",
        ),
        IdentityEvidence(
            requested_alias="blank-provider", resolved_provider_id=" ",
            resolved_model_id="fixture-model-2026-11", model_family="Other Family",
            identity_confidence="provider_reported", acquisition_mode="official_api",
        ),
        IdentityEvidence(
            requested_alias="unknown-model", resolved_provider_id="fixture-provider",
            resolved_model_id="unknown", model_family="Third Family",
            identity_confidence="provider_reported", acquisition_mode="official_api",
        ),
        IdentityEvidence(requested_alias="late-alias", inclusion="late_excluded", **confirmed),
    ]
    assert verified_family_count(identities) == 1


def test_registry_contract_rejects_duplicate_capabilities():
    with pytest.raises(ValidationError, match="Capabilities must be unique"):
        Provider(
            provider_id="fixture-provider",
            alias="fixture-alias",
            gateway="fixture-gateway",
            routing_mode="direct",
            status="enabled",
            last_verified_at=VERIFIED_AT,
            acquisition_mode="official_api",
            app_name="Fixture API",
            configured_model_id="fixture-model",
            model_family="Fixture Family",
            capabilities=["text", "text"],
            pricing_status="verified_free",
            privacy_profile="allowlisted",
            pricing_version="2026-11-09",
        )


def test_stored_original_contract_accepts_provider_output_above_manual_input_limit():
    content = "x" * 64001
    original = OriginalDetails(
        response_id=uuid4(),
        target_id=uuid4(),
        actual_model_id="fixture-model",
        model_family="Fixture Family",
        identity_confidence="provider_reported",
        acquisition_mode="official_api",
        content=content,
        source_hash="a" * 64,
        created_at=VERIFIED_AT,
        run_id=uuid4(),
        provider="fixture-provider",
        requested_model_id="fixture-model",
        gateway="fixture-gateway",
        routing_mode="direct",
        resolved_provider_id="fixture-provider",
        resolved_model_id="fixture-model",
        model_version=None,
        declared_app=None,
        declared_model_id=None,
        elapsed_ms=1,
        input_tokens=1,
        output_tokens=1,
        actual_cost_microusd=0,
        attempt_no=0,
        context_snapshot_id=None,
        inclusion="included",
    )
    assert original.content == content


def test_external_network_is_blocked_by_the_test_harness():
    with socket.socket() as connection, pytest.raises(RuntimeError, match="External test network denied"):
        connection.connect(("203.0.113.1", 443))
