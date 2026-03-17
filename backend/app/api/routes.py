from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.db import AuthError
from app.db import authenticate_user
from app.db import create_job as insert_job
from app.db import create_user
from app.db import DatabaseError
from app.db import delete_job as remove_job
from app.db import delete_session
from app.db import get_job as fetch_job
from app.db import list_jobs_page as fetch_jobs_page
from app.db import refresh_auth_tokens
from app.db import update_job as save_job
from app.schemas import AuthTokens, ErrorResponse, JobCreate, JobData, JobsPage, JobUpdate, RefreshTokenPayload, SortBy, SortOrder, UserAuthPayload, UserData
from app.storage import get_storage

router = APIRouter()


def get_current_user(request: Request) -> UserData:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.post(
    "/auth/signup",
    response_model=AuthTokens,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["auth"],
)
def sign_up(payload: UserAuthPayload) -> AuthTokens:
    try:
        return create_user(payload)
    except AuthError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/auth/login",
    response_model=AuthTokens,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["auth"],
)
def sign_in(payload: UserAuthPayload) -> AuthTokens:
    try:
        return authenticate_user(payload)
    except AuthError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@router.post(
    "/auth/refresh",
    response_model=AuthTokens,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["auth"],
)
def refresh_session(payload: RefreshTokenPayload) -> AuthTokens:
    try:
        return refresh_auth_tokens(payload.refresh_token)
    except AuthError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["auth"],
)
def logout(payload: RefreshTokenPayload) -> Response:
    delete_session(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/auth/me",
    response_model=UserData,
    responses={401: {"model": ErrorResponse}},
    tags=["auth"],
)
def get_me(user: UserData = Depends(get_current_user)) -> UserData:
    return user


@router.get("/jobs", response_model=JobsPage, tags=["jobs"])
def list_jobs(
    sort_by: SortBy = Query(default="created_at"),
    sort_order: SortOrder = Query(default="desc"),
    cursor: str | None = Query(default=None),
    user: UserData = Depends(get_current_user),
) -> JobsPage:
    try:
        return fetch_jobs_page(user.id, sort_by=sort_by, sort_order=sort_order, cursor=cursor)
    except DatabaseError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/jobs/{job_id}", response_model=JobData, tags=["jobs"])
def get_job(job_id: str, user: UserData = Depends(get_current_user)) -> JobData:
    job = fetch_job(job_id, user.id)
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
async def create_job(
    name: str = Form(..., min_length=1, max_length=120),
    file: UploadFile = File(...),
    user: UserData = Depends(get_current_user),
) -> JobData:
    if not file.filename:
        raise HTTPException(status_code=422, detail="Uploaded file must have a name")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    filename = Path(file.filename).name
    job_id = str(uuid4())
    source_object_key = f"{user.id}/{job_id}/source/{filename}"
    storage = get_storage()

    storage.upload_bytes(source_object_key, image_bytes, file.content_type)
    return insert_job(
        user.id,
        JobCreate(
            name=name,
            filename=filename,
            status="queued",
            source_object_key=source_object_key,
            content_type=file.content_type,
        ),
        job_id=job_id,
    )


@router.put(
    "/jobs/{job_id}",
    response_model=JobData,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["jobs"],
)
def update_job(job_id: str, payload: JobUpdate, user: UserData = Depends(get_current_user)) -> JobData:
    job = save_job(job_id, user.id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["jobs"],
)
def delete_job(job_id: str, user: UserData = Depends(get_current_user)) -> Response:
    deleted = remove_job(job_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}/source", tags=["jobs"])
def download_job_source(job_id: str, user: UserData = Depends(get_current_user)) -> StreamingResponse:
    job = fetch_job(job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.source_object_key:
        raise HTTPException(status_code=404, detail="Source image not found")

    data, content_type = get_storage().download_object(job.source_object_key)
    response = StreamingResponse(iter([data]), media_type=content_type or job.content_type or "application/octet-stream")
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(job.filename)}"
    return response


@router.get("/jobs/{job_id}/result", tags=["jobs"])
def download_job_result(job_id: str, user: UserData = Depends(get_current_user)) -> StreamingResponse:
    job = fetch_job(job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.result_object_key:
        raise HTTPException(status_code=409, detail="Processed image is not available yet")

    data, content_type = get_storage().download_object(job.result_object_key)
    response = StreamingResponse(iter([data]), media_type=content_type or job.result_content_type or "application/octet-stream")
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(job.filename)}"
    return response
