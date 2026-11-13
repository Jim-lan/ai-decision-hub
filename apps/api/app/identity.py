"""Provider identity rules shared by registry, reports, and tests."""

from dataclasses import dataclass
from typing import Iterable, Literal


IdentityConfidence = Literal["provider_reported", "user_declared", "unknown"]
AcquisitionMode = Literal["official_api", "manual"]
Inclusion = Literal["included", "late_excluded"]
UNKNOWN_IDENTITIES = {"", "unknown", "multi-model", "unresolved"}


@dataclass(frozen=True)
class IdentityEvidence:
    requested_alias: str
    resolved_provider_id: str | None
    resolved_model_id: str | None
    model_family: str | None
    identity_confidence: IdentityConfidence
    acquisition_mode: AcquisitionMode
    inclusion: Inclusion = "included"


def verified_family_count(identities: Iterable[IdentityEvidence]) -> int:
    """Count distinct, included families backed by attributable provider identity."""
    families = {
        identity.model_family.strip().casefold()
        for identity in identities
        if identity.inclusion == "included"
        and identity.acquisition_mode == "official_api"
        and identity.identity_confidence == "provider_reported"
        and identity.resolved_provider_id is not None
        and identity.resolved_model_id is not None
        and identity.model_family is not None
        and identity.resolved_provider_id.strip().casefold() not in UNKNOWN_IDENTITIES
        and identity.resolved_model_id.strip().casefold() not in UNKNOWN_IDENTITIES
        and identity.model_family.strip().casefold() not in UNKNOWN_IDENTITIES
    }
    return len(families)
