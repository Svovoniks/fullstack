from typing import Literal

from pydantic import BaseModel


JobStatus = Literal["queued", "processing", "completed", "failed"]


class JobSummary(BaseModel):
    id: str
    filename: str
    status: JobStatus


class JobDetails(JobSummary):
    redaction_faces: bool
    redaction_plates: bool
