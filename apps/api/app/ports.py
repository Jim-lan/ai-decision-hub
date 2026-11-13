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


@runtime_checkable
class ProviderPort(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def capabilities(self, model_id: str) -> ModelCapabilities: ...

    async def estimate_cost(self, request: GenerationRequest) -> CostEstimate: ...


class RepositoryNotFound(Exception):
    """The requested canonical record is outside the repository scope."""


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
