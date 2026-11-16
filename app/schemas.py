# app/schemas.py
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(str, Enum):
    open = "open"
    answered = "answered"
    closed = "closed"


class TicketCreate(BaseModel):  # what a client may send
    # Whitespace-only titles/bodies should not satisfy min_length.
    # Unknown keys (id, status, created_at, ...) are silently dropped by Pydantic's
    # default extra="ignore", so a client can never set them on create.
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=5, max_length=200)
    body: str = Field(min_length=10)
    fastapi_version: str | None = None


class TicketUpdate(BaseModel):  # every field optional for PATCH
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=5, max_length=200)
    status: Status | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self) -> "TicketUpdate":
        # "Omitted" means "leave unchanged"; an explicit null would wipe a
        # required field, so it is a validation error (422) instead.
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TicketOut(BaseModel):  # what the API returns
    id: int
    title: str
    body: str
    status: Status
    fastapi_version: str | None
    created_at: datetime
