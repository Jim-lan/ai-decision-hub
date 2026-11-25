"""Provider-facing P0 domain contracts with no SDK or transport dependency."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Mapping, Protocol, runtime_checkable
from uuid import UUID


FailureCode = Literal[
    "disabled",
    "policy_denied",
    "budget_denied",
    "quota_denied",
    "timeout",
    "cancelled",
    "provider_error",
    "delivery_unknown",
    "invalid_response",
    "internal_error",
]


@dataclass(frozen=True)
class GenerationRequest:
    attempt_id: UUID
    grant_id: UUID
    provider_id: str
    requested_model_id: str
    model_visible_input: str
    timeout_ms: int
    max_output_tokens: int
    allowed_model_ids: tuple[str, ...]


@dataclass(frozen=True)
class GenerationResult:
    status: Literal["succeeded", "failed"]
    requested_model_id: str
    actual_model_id: str | None
    model_family: str | None
    content: str | None
    elapsed_ms: int
    input_tokens: int | None
    output_tokens: int | None
    error_code: FailureCode | None


@dataclass(frozen=True)
class ModelCapabilities:
    model_id: str
    max_input_tokens: int
    max_output_tokens: int
    verified_at: datetime


@dataclass(frozen=True)
class CostEstimate:
    amount_microusd: int
    input_token_bound: int
    output_token_bound: int
    price_verified_at: datetime


@dataclass(frozen=True)
class ContextRequest:
    trace_id: UUID
    owner_id: UUID
    project_id: UUID
    run_id: UUID
    target_id: UUID
    provider_id: str
    alias: str
    question: str
    source_message_ids: tuple[UUID, ...]
    max_input_tokens: int
    as_of: datetime


@dataclass(frozen=True)
class ContextProjection:
    candidate_id: UUID
    policy_version: str
    source_message_ids: tuple[UUID, ...]
    model_visible_input: str
    request_hash: str
    redaction_count: int
    omission_count: int
    input_token_bound: int


@dataclass(frozen=True)
class ContextDecision:
    projection: ContextProjection | None
    reason: Literal[
        "consent_missing",
        "policy_expired",
        "recipient_blocked",
        "source_denied",
        "source_out_of_scope",
        "question_too_large",
        "candidate_conflict",
    ] | None


@dataclass(frozen=True)
class BudgetRequest:
    trace_id: UUID
    owner_id: UUID
    project_id: UUID
    run_id: UUID
    target_id: UUID
    provider_id: str
    alias: str
    reservation_key: str
    input_token_bound: int
    output_token_bound: int
    requested_run_cap_microusd: int | None
    as_of: datetime


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: UUID
    amount_microusd: int
    input_token_bound: int
    output_token_bound: int
    pricing_version: str
    owner_day: str
    owner_month: str
    provider_day: str
    state: Literal["reserved", "held", "settled", "released"]


@dataclass(frozen=True)
class BudgetDecision:
    reservation: BudgetReservation | None
    reason: Literal[
        "registry_disabled",
        "policy_missing",
        "policy_expired",
        "price_unknown",
        "request_cap",
        "run_cap",
        "day_cap",
        "month_cap",
        "provider_call_quota",
        "provider_input_quota",
        "provider_output_quota",
        "invalid_bound",
        "idempotency_conflict",
    ] | None


@dataclass(frozen=True)
class DispatchGrant:
    grant_id: UUID
    reservation_id: UUID
    candidate_id: UUID
    attempt_id: UUID
    owner_id: UUID
    project_id: UUID
    run_id: UUID
    target_id: UUID
    provider_id: str
    alias: str
    requested_model_id: str
    input_digest: str
    input_token_bound: int
    output_token_bound: int
    deadline: datetime
    validated_at: datetime


@dataclass(frozen=True)
class DispatchDecision:
    grant: DispatchGrant | None
    reason: Literal[
        "reservation_unavailable",
        "policy_expired",
        "registry_disabled",
        "period_cap",
        "provider_quota",
        "candidate_mismatch",
        "deadline",
    ] | None


@runtime_checkable
class ProviderPort(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def capabilities(self, model_id: str) -> ModelCapabilities: ...

    async def estimate_cost(self, request: GenerationRequest) -> CostEstimate: ...


@runtime_checkable
class ContextPort(Protocol):
    def prepare(self, request: ContextRequest) -> ContextDecision: ...


@runtime_checkable
class BudgetPort(Protocol):
    def reserve(self, request: BudgetRequest) -> BudgetDecision: ...

    def revalidate_dispatch(
        self,
        reservation_id: UUID,
        candidate_id: UUID,
        attempt_id: UUID,
        trace_id: UUID,
        as_of: datetime,
    ) -> DispatchDecision: ...

    def reconcile(
        self,
        reservation_id: UUID,
        trace_id: UUID,
        *,
        outcome: Literal["release", "settle", "hold"],
        proven_unsent: bool = False,
        actual_cost_microusd: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> BudgetReservation: ...


@runtime_checkable
class AuthorizationPort(Protocol):
    def validate_dispatch(self, request: GenerationRequest, as_of: datetime) -> DispatchGrant: ...


class RepositoryNotFound(Exception):
    """The requested canonical record is outside the repository scope."""


class RepositoryConflict(Exception):
    """The requested mutation conflicts with immutable canonical state."""


@dataclass(frozen=True)
class ManualOriginalCommand:
    trace_id: UUID
    owner_id: UUID
    run_id: UUID
    target_id: UUID
    content: str
    model_family: str
    declared_app: str | None
    declared_model_id: str | None


@dataclass(frozen=True)
class ManualOriginalResult:
    original: Mapping[str, object]
    project_id: UUID
    created: bool


@dataclass(frozen=True)
class WorkClaim:
    run_id: UUID
    owner_id: UUID
    project_id: UUID
    lease_token: UUID
    fence: int
    deadline: datetime


@dataclass(frozen=True)
class DispatchWork:
    run_id: UUID
    target_id: UUID
    reservation_id: UUID
    attempt_id: UUID
    request: GenerationRequest


@runtime_checkable
class ConversationRepository(Protocol):
    """Canonical owner/project/conversation/message persistence boundary."""

    def create_project(self, owner_id: UUID, name: str) -> Mapping[str, object]: ...

    def list_projects(self, owner_id: UUID) -> list[Mapping[str, object]]: ...

    def get_project(self, project_id: UUID, owner_id: UUID) -> Mapping[str, object]: ...

    def create_conversation(self, project_id: UUID, title: str) -> Mapping[str, object]: ...

    def list_conversations(self, project_id: UUID) -> list[Mapping[str, object]]: ...

    def get_conversation(
        self, conversation_id: UUID, owner_id: UUID, *, lock: bool = False
    ) -> Mapping[str, object]: ...

    def append_message(self, conversation_id: UUID, content: str) -> Mapping[str, object]: ...

    def list_messages(
        self, conversation_id: UUID, after_sequence: int, limit: int
    ) -> list[Mapping[str, object]]: ...

    def has_search_anchor(
        self, project_id: UUID, resource_id: UUID, created_at: datetime, query: str
    ) -> bool: ...

    def search_messages(
        self,
        project_id: UUID,
        query: str,
        after_created: datetime,
        after_kind: str,
        after_resource: UUID,
        limit: int,
    ) -> list[Mapping[str, object]]: ...


@runtime_checkable
class RunRepository(Protocol):
    """Canonical owner-scoped run and immutable-original persistence boundary."""

    def get_run(self, run_id: UUID, owner_id: UUID) -> Mapping[str, object]: ...

    def list_originals(
        self, run_id: UUID, owner_id: UUID
    ) -> list[Mapping[str, object]]: ...

    def list_events(
        self, run_id: UUID, owner_id: UUID, after: int, limit: int
    ) -> list[Mapping[str, object]]: ...

    def settle_deadline(
        self, run_id: UUID, owner_id: UUID, trace_id: UUID
    ) -> Mapping[str, object]: ...

    def cancel_run(
        self, run_id: UUID, owner_id: UUID, trace_id: UUID
    ) -> Mapping[str, object]: ...

    def claim_work(
        self, worker_id: str, trace_id: UUID, lease_seconds: int
    ) -> WorkClaim | None: ...

    def park_manual_work(self, claim: WorkClaim, trace_id: UUID) -> bool: ...

    def prepare_next_dispatch(
        self, claim: WorkClaim, trace_id: UUID
    ) -> DispatchWork | None: ...

    def recover_claimed_dispatches(
        self, claim: WorkClaim, trace_id: UUID
    ) -> int: ...

    def import_manual_original(
        self, command: ManualOriginalCommand
    ) -> ManualOriginalResult: ...
