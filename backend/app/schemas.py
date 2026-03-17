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
    source_object_key: str | None = None
    result_object_key: str | None = None
    content_type: str | None = None
    result_content_type: str | None = None
    error_message: str | None = None


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=255)
    status: JobStatus = "queued"
    source_object_key: str | None = Field(default=None, max_length=1024)
    result_object_key: str | None = Field(default=None, max_length=1024)
    content_type: str | None = Field(default=None, max_length=255)
    result_content_type: str | None = Field(default=None, max_length=255)
    error_message: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(str_strip_whitespace=True)


class JobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    status: JobStatus | None = None
    source_object_key: str | None = Field(default=None, max_length=1024)
    result_object_key: str | None = Field(default=None, max_length=1024)
    content_type: str | None = Field(default=None, max_length=255)
    result_content_type: str | None = Field(default=None, max_length=255)
    error_message: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "JobUpdate":
        if (
            self.name is None
            and self.filename is None
            and self.status is None
            and self.source_object_key is None
            and self.result_object_key is None
            and self.content_type is None
            and self.result_content_type is None
            and self.error_message is None
        ):
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
