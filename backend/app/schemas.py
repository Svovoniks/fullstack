from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


JobStatus = Literal["queued", "processing", "completed", "failed"]
SortBy = Literal["created_at", "id", "name", "status", "filename"]
SortOrder = Literal["asc", "desc"]


class JobData(BaseModel):
    id: str
    name: str
    filename: str
    status: JobStatus
    created_at: datetime


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=255)
    status: JobStatus = "queued"

    model_config = ConfigDict(str_strip_whitespace=True)


class JobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    status: JobStatus | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "JobUpdate":
        if self.name is None and self.filename is None and self.status is None:
            raise ValueError("At least one field must be provided")

        return self


class ErrorResponse(BaseModel):
    detail: str


class UserAuthPayload(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserData(BaseModel):
    id: str
    username: str
    created_at: datetime


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserData


class RefreshTokenPayload(BaseModel):
    refresh_token: str = Field(min_length=20)

    model_config = ConfigDict(str_strip_whitespace=True)
