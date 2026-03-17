from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Final
from uuid import uuid4

from psycopg import connect
from psycopg.rows import dict_row

from app.schemas import (
    AuthTokens,
    JobCreate,
    JobData,
    JobUpdate,
    SortBy,
    SortOrder,
    UserAuthPayload,
    UserData,
)
from app.security import create_access_token, create_refresh_token, hash_password, verify_password

SORT_COLUMN_MAP: Final[dict[SortBy, str]] = {
    "created_at": "created_at",
    "id": "id",
    "name": "name",
    "status": "status",
    "filename": "filename",
}

SORT_DIRECTION_MAP: Final[dict[SortOrder, str]] = {
    "asc": "ASC",
    "desc": "DESC",
}

class DatabaseError(Exception):
    pass


class AuthError(Exception):
    pass


def get_connection():
    return connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "redaction"),
        user=os.getenv("POSTGRES_USER", "redaction"),
        password=os.getenv("POSTGRES_PASSWORD", "redaction"),
        row_factory=dict_row,
    )


def _execute_fetchall(query: str, params: tuple[object, ...] = ()) -> list[dict]:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
    except Exception as error:
        raise DatabaseError("Database operation failed") from error


def _execute_fetchone(query: str, params: tuple[object, ...] = ()) -> dict | None:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
    except Exception as error:
        raise DatabaseError("Database operation failed") from error


def _execute_commit(query: str, params: tuple[object, ...] = ()) -> dict | None:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
            connection.commit()
            return row
    except Exception as error:
        raise DatabaseError("Database operation failed") from error


def _execute_commit_without_return(query: str, params: tuple[object, ...] = ()) -> None:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
            connection.commit()
    except Exception as error:
        raise DatabaseError("Database operation failed") from error

def list_jobs(user_id: str, sort_by: SortBy, sort_order: SortOrder) -> list[JobData]:
    sort_column = SORT_COLUMN_MAP[sort_by]
    sort_direction = SORT_DIRECTION_MAP[sort_order]
    query = f"""
        SELECT id, name, filename, status, created_at
        FROM jobs
        WHERE user_id = %s
        ORDER BY {sort_column} {sort_direction}, id ASC
    """
    rows = _execute_fetchall(query, (user_id,))
    return [JobData.model_validate(dict(row)) for row in rows]


def get_job(job_id: str, user_id: str) -> JobData | None:
    row = _execute_fetchone(
        "SELECT id, name, filename, status, created_at FROM jobs WHERE id = %s AND user_id = %s",
        (job_id, user_id),
    )
    if row is None:
        return None
    return JobData.model_validate(dict(row))


def create_job(user_id: str, payload: JobCreate) -> JobData:
    row = _execute_commit(
        """
        INSERT INTO jobs (id, user_id, name, filename, status, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id, name, filename, status, created_at
        """,
        (str(uuid4()), user_id, payload.name, payload.filename, payload.status),
    )
    if row is None:
        raise DatabaseError("Failed to create job")
    return JobData.model_validate(dict(row))


def update_job(job_id: str, user_id: str, payload: JobUpdate) -> JobData | None:
    current_job = get_job(job_id, user_id)
    if current_job is None:
        return None

    row = _execute_commit(
        """
        UPDATE jobs
        SET name = %s, filename = %s, status = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, name, filename, status, created_at
        """,
        (
            payload.name if payload.name is not None else current_job.name,
            payload.filename if payload.filename is not None else current_job.filename,
            payload.status if payload.status is not None else current_job.status,
            job_id,
            user_id,
        ),
    )
    if row is None:
        return None
    return JobData.model_validate(dict(row))


def delete_job(job_id: str, user_id: str) -> bool:
    row = _execute_commit("DELETE FROM jobs WHERE id = %s AND user_id = %s RETURNING id", (job_id, user_id))
    return row is not None


def _build_auth_tokens(user_row: dict) -> AuthTokens:
    access_token, access_expires_at = create_access_token(user_row["id"], user_row["username"])
    refresh_token, refresh_expires_at = create_refresh_token()
    _execute_commit_without_return(
        """
        INSERT INTO user_sessions (id, user_id, refresh_token, expires_at, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (str(uuid4()), user_row["id"], refresh_token, refresh_expires_at),
    )
    return AuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=access_expires_at,
        user=UserData.model_validate(
            {
                "id": user_row["id"],
                "username": user_row["username"],
                "created_at": user_row["created_at"],
            }
        ),
    )


def create_user(payload: UserAuthPayload) -> AuthTokens:
    existing_user = _execute_fetchone("SELECT id FROM users WHERE username = %s", (payload.username,))
    if existing_user is not None:
        raise AuthError("Username is already taken")

    row = _execute_commit(
        """
        INSERT INTO users (id, username, password_hash, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id, username, created_at
        """,
        (str(uuid4()), payload.username, hash_password(payload.password)),
    )
    if row is None:
        raise DatabaseError("Failed to create user")
    return _build_auth_tokens(dict(row))


def authenticate_user(payload: UserAuthPayload) -> AuthTokens:
    row = _execute_fetchone(
        "SELECT id, username, password_hash, created_at FROM users WHERE username = %s",
        (payload.username,),
    )
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise AuthError("Invalid username or password")

    return _build_auth_tokens(dict(row))


def refresh_auth_tokens(refresh_token: str) -> AuthTokens:
    row = _execute_fetchone(
        """
        SELECT s.id AS session_id, s.user_id, s.refresh_token, s.expires_at, u.username, u.created_at
        FROM user_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.refresh_token = %s
        """,
        (refresh_token,),
    )
    if row is None:
        raise AuthError("Invalid refresh token")

    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        _execute_commit_without_return("DELETE FROM user_sessions WHERE id = %s", (row["session_id"],))
        raise AuthError("Refresh token expired")

    _execute_commit_without_return("DELETE FROM user_sessions WHERE id = %s", (row["session_id"],))
    return _build_auth_tokens(
        {
            "id": row["user_id"],
            "username": row["username"],
            "created_at": row["created_at"],
        }
    )


def get_user_by_id(user_id: str) -> UserData | None:
    row = _execute_fetchone(
        "SELECT id, username, created_at FROM users WHERE id = %s",
        (user_id,),
    )
    if row is None:
        return None
    return UserData.model_validate(dict(row))


def delete_session(refresh_token: str) -> None:
    _execute_commit_without_return("DELETE FROM user_sessions WHERE refresh_token = %s", (refresh_token,))
