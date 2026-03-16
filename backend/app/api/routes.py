from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from app.db import AuthError
from app.db import authenticate_user
from app.db import create_job as insert_job
from app.db import create_user
from app.db import delete_job as remove_job
from app.db import delete_session
from app.db import get_job as fetch_job
from app.db import get_user_by_id
from app.db import list_jobs as fetch_jobs
from app.db import refresh_auth_tokens
from app.db import update_job as save_job
from app.schemas import AuthTokens, ErrorResponse, JobCreate, JobData, JobUpdate, RefreshTokenPayload, SortBy, SortOrder, UserAuthPayload, UserData
from app.security import decode_access_token

router = APIRouter()


def get_current_user(authorization: str = Header(default="")) -> UserData:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", maxsplit=1)[1]

    try:
        payload = decode_access_token(token)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error

    user = get_user_by_id(str(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

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
    _: UserData = Depends(get_current_user),
) -> list[JobData]:
    return fetch_jobs(sort_by=sort_by, sort_order=sort_order)


@router.get("/jobs/{job_id}", response_model=JobData, tags=["jobs"])
def get_job(job_id: str, _: UserData = Depends(get_current_user)) -> JobData:
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
def create_job(payload: JobCreate, _: UserData = Depends(get_current_user)) -> JobData:
    return insert_job(payload)


@router.put(
    "/jobs/{job_id}",
    response_model=JobData,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["jobs"],
)
def update_job(job_id: str, payload: JobUpdate, _: UserData = Depends(get_current_user)) -> JobData:
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
def delete_job(job_id: str, _: UserData = Depends(get_current_user)) -> Response:
    deleted = remove_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
