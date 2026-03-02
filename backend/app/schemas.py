from typing import Literal

from pydantic import BaseModel


JobStatus = Literal["queued", "processing", "completed", "failed"]


class JobData(BaseModel):
    id: str
    name: str
    filename: str
    status: JobStatus
