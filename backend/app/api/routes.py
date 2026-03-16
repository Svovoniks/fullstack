from fastapi import APIRouter, HTTPException, Query, Response, status

from app.db import create_job as insert_job
from app.db import delete_job as remove_job
from app.db import get_job as fetch_job
from app.db import list_jobs as fetch_jobs
from app.db import update_job as save_job
from app.schemas import ErrorResponse, JobCreate, JobData, JobUpdate, SortBy, SortOrder

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


@router.post(
    "/jobs",
    response_model=JobData,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["jobs"],
)
def create_job(payload: JobCreate) -> JobData:
    return insert_job(payload)


@router.put(
    "/jobs/{job_id}",
    response_model=JobData,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["jobs"],
)
def update_job(job_id: str, payload: JobUpdate) -> JobData:
    job = save_job(job_id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["jobs"],
)
def delete_job(job_id: str) -> Response:
    deleted = remove_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
