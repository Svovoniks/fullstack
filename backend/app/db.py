from __future__ import annotations

import os
import time
from typing import Final

from psycopg import connect
from psycopg.rows import dict_row

from app.schemas import JobData, SortBy, SortOrder

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


def get_connection():
    return connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "redaction"),
        user=os.getenv("POSTGRES_USER", "redaction"),
        password=os.getenv("POSTGRES_PASSWORD", "redaction"),
        row_factory=dict_row,
    )


def init_db() -> None:
    last_error: Exception | None = None

    for _ in range(10):
        try:
            with get_connection() as connection:
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

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [JobData.model_validate(dict(row)) for row in rows]


def get_job(job_id: str) -> JobData | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, filename, status, created_at FROM jobs WHERE id = %s",
                (job_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    return JobData.model_validate(dict(row))
