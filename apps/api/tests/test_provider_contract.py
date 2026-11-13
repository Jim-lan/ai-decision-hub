import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from uuid import uuid4

from jsonschema import Draft202012Validator
import pytest

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


def test_external_network_is_blocked_by_the_test_harness():
    with socket.socket() as connection, pytest.raises(RuntimeError, match="External test network denied"):
        connection.connect(("203.0.113.1", 443))
