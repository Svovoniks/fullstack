from fastapi import APIRouter

from app.schemas import JobData, JobStatus

router = APIRouter()


@router.get("/jobs", response_model=list[JobData], tags=["jobs"])
def list_jobs() -> list[JobData]:
    return [
    ]


@router.get("/jobs/{job_id}", response_model=JobData, tags=["jobs"])
def get_job(job_id: str) -> JobData:
    return JobData(
        id=job_id,
        name="name",
        filename="file",
        status="completed",
    )
