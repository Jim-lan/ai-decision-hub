"""Validate versioned API documents and positive/negative response fixtures."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs/testing/fixtures/openapi"


def load_json(path: Path):
    return json.loads(path.read_text())


def response_validator(specification: dict) -> Draft202012Validator:
    response = specification["paths"]["/v1/providers"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    response_contract = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": specification["components"],
        "allOf": [response],
    }
    return Draft202012Validator(response_contract)


def assert_fixture_pair(
    validator: Draft202012Validator, valid_name: str, incompatible_name: str
) -> None:
    if errors := list(validator.iter_errors(load_json(FIXTURES / valid_name))):
        raise SystemExit(f"Valid provider response fixture failed: {errors[0].message}")
    if not list(validator.iter_errors(load_json(FIXTURES / incompatible_name))):
        raise SystemExit("Intentionally incompatible provider response fixture was accepted")


def main() -> None:
    candidate_path = ROOT / "docs/api/openapi.yaml"
    candidate = yaml.safe_load(candidate_path.read_text())
    runtime = load_json(ROOT / "contracts/openapi.json")
    validate(candidate, base_uri=candidate_path.parent.as_uri() + "/")
    validate(runtime)

    for label, specification in (("candidate", candidate), ("runtime", runtime)):
        off_version = sorted(path for path in specification["paths"] if not path.startswith("/v1"))
        if off_version:
            raise SystemExit(f"{label} OpenAPI contains unversioned paths: {off_version}")

    assert_fixture_pair(
        response_validator(runtime), "providers-valid.json", "providers-incompatible.json"
    )
    assert_fixture_pair(
        response_validator(candidate),
        "providers-candidate-valid.json",
        "providers-candidate-incompatible.json",
    )
    print("Candidate/runtime OpenAPI valid; incompatible response fixture rejected")


if __name__ == "__main__":
    main()
