from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


class Provider(BaseModel):
    provider_id: str
    alias: str
    gateway: str
    routing_mode: str
    status: str
    last_verified_at: datetime | None


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


class StoredOriginal(BaseModel):
    response_id: UUID
    target_id: UUID
    actual_model_id: str
    model_family: str
    identity_confidence: str
    acquisition_mode: str
    content: str
    source_hash: str
    created_at: datetime


class OriginalDetails(StoredOriginal):
    run_id: UUID
    provider: str
    requested_model_id: str
    gateway: str
    routing_mode: str
