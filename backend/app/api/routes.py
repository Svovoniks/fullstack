from fastapi import APIRouter, HTTPException

from app.schemas import JobDetails, JobSummary

router = APIRouter()

JOBS: dict[str, JobDetails] = {
    "job_001": JobDetails(
        id="job_001",
        filename="street-01.jpg",
        status="completed",
        redaction_faces=True,
        redaction_plates=True,
    ),
    "job_002": JobDetails(
        id="job_002",
        filename="doc-scan.png",
        status="processing",
        redaction_faces=True,
        redaction_plates=True,
    ),
}


@router.get("/jobs", response_model=list[JobSummary], tags=["jobs"])
def list_jobs() -> list[JobSummary]:
    return [
        JobSummary(id=job.id, filename=job.filename, status=job.status)
        for job in JOBS.values()
    ]


@router.get("/jobs/{job_id}", response_model=JobDetails, tags=["jobs"])
def get_job(job_id: str) -> JobDetails:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
