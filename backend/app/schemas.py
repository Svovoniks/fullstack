from typing import Literal

from pydantic import BaseModel


JobStatus = Literal["queued", "processing", "completed", "failed"]
SortBy = Literal["created_at", "id", "name", "status", "filename"]
SortOrder = Literal["asc", "desc"]


class JobData(BaseModel):
    id: str
    name: str
    filename: str
    status: JobStatus
    created_at: str
