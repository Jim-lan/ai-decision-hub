from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


NonBlank160 = Annotated[str, Field(min_length=1, max_length=160, pattern=r"\S")]
NonNegativeInt = Annotated[int, Field(ge=0)]


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class Named(BaseModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def require_name(cls, value):
        if not value.strip():
            raise ValueError("Enter a name")
        return value.strip()


class NewConversation(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=160, pattern=r"\S")


class NewMessage(BaseModel):
    content: str = Field(min_length=1, max_length=64000, pattern=r"\S")


class Project(BaseModel):
    project_id: UUID
    name: str
    created_at: datetime


class Conversation(BaseModel):
    conversation_id: UUID
    project_id: UUID
    title: str
    created_at: datetime


class Message(BaseModel):
    message_id: UUID
    conversation_id: UUID
    sequence: int
    role: str
    content: str
    source_hash: str
    created_at: datetime


class History(BaseModel):
    items: list[Message]
    next_cursor: str | None


class SearchHit(BaseModel):
    project_id: UUID
    conversation_id: UUID
    kind: Literal["message", "decision"]
    resource_id: UUID
    run_id: UUID | None
    excerpt: str = Field(max_length=240)
    created_at: datetime


class SearchPage(BaseModel):
    items: list[SearchHit]
    next_cursor: str | None


class Provider(BaseModel):
    provider_id: NonBlank160
    alias: NonBlank160
    gateway: NonBlank160
    routing_mode: NonBlank160
    status: Literal["enabled", "disabled"]
    last_verified_at: datetime | None
    acquisition_mode: Literal["official_api", "manual"]
    app_name: NonBlank160 | None
    configured_model_id: NonBlank160 | None
    model_family: NonBlank160 | None
    capabilities: list[Literal["text", "manual_import"]] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    pricing_status: Literal["verified_free", "verified_priced", "unknown", "manual"]
    privacy_profile: Literal["local_only", "allowlisted", "blocked"]
    pricing_version: NonBlank160 | None

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Capabilities must be unique")
        return value


class TargetStatus(BaseModel):
    target_id: UUID
    provider: str
    model_id: str
    gateway: str
    routing_mode: str
    response_id: UUID | None
    status: str


class Run(BaseModel):
    run_id: UUID
    conversation_id: UUID
    message_id: UUID
    created_at: datetime
    deadline: datetime
    status: str
    targets: list[TargetStatus]
    links: dict[str, str]


class UsageWindow(BaseModel):
    cap_microusd: NonNegativeInt
    reserved_microusd: NonNegativeInt
    held_microusd: NonNegativeInt
    settled_microusd: NonNegativeInt
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None


class Usage(BaseModel):
    currency: Literal["USD"]
    as_of: datetime
    day: UsageWindow
    month: UsageWindow
    run: UsageWindow | None


class StoredOriginal(BaseModel):
    response_id: UUID
    target_id: UUID
    actual_model_id: NonBlank160
    model_family: NonBlank160
    identity_confidence: Literal["provider_reported", "user_declared", "unknown"]
    acquisition_mode: Literal["official_api", "manual"]
    content: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class OriginalDetails(StoredOriginal):
    run_id: UUID
    provider: NonBlank160
    requested_model_id: NonBlank160
    gateway: NonBlank160
    routing_mode: NonBlank160
    resolved_provider_id: NonBlank160 | None
    resolved_model_id: NonBlank160 | None
    model_version: NonBlank160 | None
    declared_app: NonBlank160 | None
    declared_model_id: NonBlank160 | None
    elapsed_ms: NonNegativeInt | None
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None
    actual_cost_microusd: NonNegativeInt | None
    attempt_no: NonNegativeInt
    context_snapshot_id: UUID | None
    inclusion: Literal["included", "late_excluded"]
