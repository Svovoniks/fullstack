from __future__ import annotations

import os

import httpx


class ProcessingError(Exception):
    pass


class ImageProcessor:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def redact(self, filename: str, content_type: str, file_bytes: bytes) -> tuple[bytes, str]:
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.base_url}/redact",
                    files={"file": (filename, file_bytes, content_type)},
                )
        except httpx.HTTPError as error:
            raise ProcessingError("Failed to reach the image processing service") from error

        if response.status_code >= 400:
            detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else None
            raise ProcessingError(detail or "Image processing failed")

        return response.content, response.headers.get("content-type", "image/jpeg")


def get_image_processor() -> ImageProcessor:
    return ImageProcessor(os.getenv("YOLO_SERVICE_URL", "http://yolo-service:8000"))
