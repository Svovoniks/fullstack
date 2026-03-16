from fastapi import APIRouter, HTTPException, Query

from app.db import get_job as fetch_job
from app.db import list_jobs as fetch_jobs
from app.schemas import JobData, SortBy, SortOrder

router = APIRouter()


@router.get("/jobs", response_model=list[JobData], tags=["jobs"])
def list_jobs(
    sort_by: SortBy = Query(default="created_at"),
    sort_order: SortOrder = Query(default="desc"),
) -> list[JobData]:
    return fetch_jobs(sort_by=sort_by, sort_order=sort_order)


@router.get("/jobs/{job_id}", response_model=JobData, tags=["jobs"])
def get_job(job_id: str) -> JobData:
    job = fetch_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job
