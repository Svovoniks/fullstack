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

DEFAULT_ADMIN_USERNAME: Final[str] = "admin"
DEFAULT_ADMIN_PASSWORD_HASH: Final[str] = "100000$OWWBT0KnAkj07QqlYNSecw==$1D89gEkPsGX5q3a69TtpudsQ2QrF5cQPW21LMcYVfWw="

class DatabaseError(Exception):
    pass


class AuthError(Exception):
    pass


def _job_columns(table_name: str = "jobs") -> str:
    return """
        {table_name}.id AS id,
        {table_name}.user_id AS user_id,
        {table_name}.name AS name,
        {table_name}.filename AS filename,
        {table_name}.status AS status,
        {table_name}.created_at AS created_at,
        {table_name}.source_object_key AS source_object_key,
        {table_name}.result_object_key AS result_object_key,
        {table_name}.content_type AS content_type,
        {table_name}.result_content_type AS result_content_type,
        {table_name}.error_message AS error_message
    """.format(table_name=table_name)


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

def ensure_schema() -> None:
    _execute_commit_without_return(
        """
        ALTER TABLE jobs
        ADD COLUMN IF NOT EXISTS source_object_key TEXT,
        ADD COLUMN IF NOT EXISTS result_object_key TEXT,
        ADD COLUMN IF NOT EXISTS content_type TEXT,
        ADD COLUMN IF NOT EXISTS result_content_type TEXT,
        ADD COLUMN IF NOT EXISTS error_message TEXT
        """
    )


def ensure_default_admin_user() -> None:
    _execute_commit_without_return(
        """
        INSERT INTO users (id, username, password_hash, created_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (username) DO NOTHING
        """,
        (str(uuid4()), DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD_HASH),
    )


def list_jobs(user_id: str, sort_by: SortBy, sort_order: SortOrder) -> list[JobData]:
    sort_column = SORT_COLUMN_MAP[sort_by]
    sort_direction = SORT_DIRECTION_MAP[sort_order]
    query = f"""
        SELECT id, name, filename, status, created_at, source_object_key, result_object_key, content_type, result_content_type, error_message
        FROM jobs
        WHERE user_id = %s
        ORDER BY {sort_column} {sort_direction}, id ASC
    """
    rows = _execute_fetchall(query, (user_id,))
    return [JobData.model_validate(dict(row)) for row in rows]


def get_job(job_id: str, user_id: str) -> JobData | None:
    row = _execute_fetchone(
        """
        SELECT id, name, filename, status, created_at, source_object_key, result_object_key, content_type, result_content_type, error_message
        FROM jobs
        WHERE id = %s AND user_id = %s
        """,
        (job_id, user_id),
    )
    if row is None:
        return None
    return JobData.model_validate(dict(row))


def create_job(user_id: str, payload: JobCreate, job_id: str | None = None) -> JobData:
    row = _execute_commit(
        """
        INSERT INTO jobs (
            id, user_id, name, filename, status, created_at, source_object_key, result_object_key, content_type, result_content_type, error_message
        )
        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
        RETURNING id, name, filename, status, created_at, source_object_key, result_object_key, content_type, result_content_type, error_message
        """,
        (
            job_id or str(uuid4()),
            user_id,
            payload.name,
            payload.filename,
            payload.status,
            payload.source_object_key,
            payload.result_object_key,
            payload.content_type,
            payload.result_content_type,
            payload.error_message,
        ),
    )
    if row is None:
        raise DatabaseError("Failed to create job")
    return JobData.model_validate(dict(row))


def claim_next_queued_job() -> dict | None:
    row = _execute_commit(
        f"""
        WITH next_job AS (
            SELECT id
            FROM jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC, id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE jobs
        SET
            status = 'processing',
            error_message = NULL
        FROM next_job
        WHERE jobs.id = next_job.id
        RETURNING {_job_columns()}
        """
    )
    if row is None:
        return None
    return dict(row)


def update_job_processing_state(job_id: str, payload: JobUpdate) -> JobData | None:
    row = _execute_commit(
        """
        UPDATE jobs
        SET
            status = COALESCE(%s, status),
            source_object_key = COALESCE(%s, source_object_key),
            result_object_key = COALESCE(%s, result_object_key),
            content_type = COALESCE(%s, content_type),
            result_content_type = COALESCE(%s, result_content_type),
            error_message = COALESCE(%s, error_message)
        WHERE id = %s
        RETURNING id, name, filename, status, created_at, source_object_key, result_object_key, content_type, result_content_type, error_message
        """,
        (
            payload.status,
            payload.source_object_key,
            payload.result_object_key,
            payload.content_type,
            payload.result_content_type,
            payload.error_message,
            job_id,
        ),
    )
    if row is None:
        return None
    return JobData.model_validate(dict(row))


def requeue_in_progress_jobs() -> None:
    _execute_commit_without_return(
        """
        UPDATE jobs
        SET
            status = 'queued',
            error_message = NULL
        WHERE status = 'processing'
        """
    )


def update_job(job_id: str, user_id: str, payload: JobUpdate) -> JobData | None:
    current_job = get_job(job_id, user_id)
    if current_job is None:
        return None

    row = _execute_commit(
        """
        UPDATE jobs
        SET
            name = %s,
            filename = %s,
            status = %s,
            source_object_key = %s,
            result_object_key = %s,
            content_type = %s,
            result_content_type = %s,
            error_message = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, name, filename, status, created_at, source_object_key, result_object_key, content_type, result_content_type, error_message
        """,
        (
            payload.name if payload.name is not None else current_job.name,
            payload.filename if payload.filename is not None else current_job.filename,
            payload.status if payload.status is not None else current_job.status,
            payload.source_object_key if payload.source_object_key is not None else current_job.source_object_key,
            payload.result_object_key if payload.result_object_key is not None else current_job.result_object_key,
            payload.content_type if payload.content_type is not None else current_job.content_type,
            payload.result_content_type if payload.result_content_type is not None else current_job.result_content_type,
            payload.error_message if payload.error_message is not None else current_job.error_message,
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
