from __future__ import annotations

import logging
import threading

from app.db import claim_next_queued_job, requeue_in_progress_jobs, update_job_processing_state
from app.processing import ProcessingError, get_image_processor
from app.schemas import JobUpdate
from app.storage import get_storage

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self, poll_interval: float = 1.0) -> None:
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        requeue_in_progress_jobs()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            job = claim_next_queued_job()
            if job is None:
                self._stop_event.wait(self.poll_interval)
                continue

            self._process_job(job)

    def _process_job(self, job: dict) -> None:
        storage = get_storage()
        processor = get_image_processor()

        try:
            if not job.get("source_object_key"):
                raise ProcessingError("Source image is missing")
            if not job.get("content_type"):
                raise ProcessingError("Source content type is missing")

            image_bytes, stored_content_type = storage.download_object(job["source_object_key"])
            result_bytes, result_content_type = processor.redact(
                job["filename"],
                stored_content_type or job["content_type"],
                image_bytes,
            )

            result_object_key = f"{job['user_id']}/{job['id']}/result/{job['filename']}"
            storage.upload_bytes(result_object_key, result_bytes, result_content_type)

            update_job_processing_state(
                job["id"],
                JobUpdate(
                    status="completed",
                    result_object_key=result_object_key,
                    result_content_type=result_content_type,
                    error_message="",
                ),
            )
        except ProcessingError as error:
            logger.warning("Job %s failed during processing: %s", job["id"], error)
            update_job_processing_state(job["id"], JobUpdate(status="failed", error_message=str(error)))
        except Exception:
            logger.exception("Job %s failed with an unexpected error", job["id"])
            update_job_processing_state(job["id"], JobUpdate(status="failed", error_message="Processing failed"))
