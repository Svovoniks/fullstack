from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.db import AuthError
from app.db import authenticate_user
from app.db import create_job as insert_job
from app.db import create_user
from app.db import delete_job as remove_job
from app.db import delete_session
from app.db import get_job as fetch_job
from app.db import list_jobs as fetch_jobs
from app.db import refresh_auth_tokens
from app.db import update_job as save_job
from app.schemas import AuthTokens, ErrorResponse, JobCreate, JobData, JobUpdate, RefreshTokenPayload, SortBy, SortOrder, UserAuthPayload, UserData

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


@router.get("/jobs", response_model=list[JobData], tags=["jobs"])
def list_jobs(
    sort_by: SortBy = Query(default="created_at"),
    sort_order: SortOrder = Query(default="desc"),
    user: UserData = Depends(get_current_user),
) -> list[JobData]:
    return fetch_jobs(user.id, sort_by=sort_by, sort_order=sort_order)


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
def create_job(payload: JobCreate, user: UserData = Depends(get_current_user)) -> JobData:
    return insert_job(user.id, payload)


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
