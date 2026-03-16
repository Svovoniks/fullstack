from __future__ import annotations

import os
import time
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

SEED_JOBS: Final[list[tuple[str, str, str, str, str]]] = [
    ("2f37f63b-7341-46e6-80d7-2d23d373efca", "parking-cam-01", "parking-cam-01.mp4", "completed", "2026-03-16T09:15:00Z"),
    ("0103fae2-c950-489d-b6b8-ead4de6e3a6f", "office-entrance", "office-entrance.zip", "processing", "2026-03-16T08:50:00Z"),
    ("7cc087f9-d212-4e19-a0de-40ae46d5d920", "passport-scan", "passport-scan.pdf", "queued", "2026-03-16T08:10:00Z"),
    ("cd4d31ef-7724-463c-82ea-8b091f75a6e0", "street-photo", "street-photo.jpg", "failed", "2026-03-15T18:25:00Z"),
]


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


def _create_tables(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                filename TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                refresh_token TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )


def init_db() -> None:
    last_error: Exception | None = None

    for _ in range(10):
        try:
            with get_connection() as connection:
                _create_tables(connection)
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO jobs (id, name, filename, status, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        SEED_JOBS,
                    )
                connection.commit()
                return
        except Exception as error:
            last_error = error
            time.sleep(1)

    if last_error is not None:
        raise last_error


def list_jobs(sort_by: SortBy, sort_order: SortOrder) -> list[JobData]:
    sort_column = SORT_COLUMN_MAP[sort_by]
    sort_direction = SORT_DIRECTION_MAP[sort_order]
    query = f"""
        SELECT id, name, filename, status, created_at
        FROM jobs
        ORDER BY {sort_column} {sort_direction}, id ASC
    """
    rows = _execute_fetchall(query)
    return [JobData.model_validate(dict(row)) for row in rows]


def get_job(job_id: str) -> JobData | None:
    row = _execute_fetchone(
        "SELECT id, name, filename, status, created_at FROM jobs WHERE id = %s",
        (job_id,),
    )
    if row is None:
        return None
    return JobData.model_validate(dict(row))


def create_job(payload: JobCreate) -> JobData:
    row = _execute_commit(
        """
        INSERT INTO jobs (id, name, filename, status, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id, name, filename, status, created_at
        """,
        (str(uuid4()), payload.name, payload.filename, payload.status),
    )
    if row is None:
        raise DatabaseError("Failed to create job")
    return JobData.model_validate(dict(row))


def update_job(job_id: str, payload: JobUpdate) -> JobData | None:
    current_job = get_job(job_id)
    if current_job is None:
        return None

    row = _execute_commit(
        """
        UPDATE jobs
        SET name = %s, filename = %s, status = %s
        WHERE id = %s
        RETURNING id, name, filename, status, created_at
        """,
        (
            payload.name if payload.name is not None else current_job.name,
            payload.filename if payload.filename is not None else current_job.filename,
            payload.status if payload.status is not None else current_job.status,
            job_id,
        ),
    )
    if row is None:
        return None
    return JobData.model_validate(dict(row))


def delete_job(job_id: str) -> bool:
    row = _execute_commit("DELETE FROM jobs WHERE id = %s RETURNING id", (job_id,))
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
