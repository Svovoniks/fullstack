from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


@dataclass(frozen=True)
class DetectorConfig:
    face_model_path: str
    license_plate_model_path: str
    device: str
    face_confidence: float
    license_plate_confidence: float


@dataclass(frozen=True)
class RedactionSummary:
    faces: int
    license_plates: int

    @property
    def total(self) -> int:
        return self.faces + self.license_plates


class RedactionService:
    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self.face_model = self._load_model(config.face_model_path, "face")
        self.license_plate_model = self._load_model(config.license_plate_model_path, "license plate")

    def _load_model(self, model_path: str, label: str) -> YOLO:
        if not self._is_model_reference_usable(model_path):
            raise RuntimeError(
                f"Missing {label} model at '{model_path}'. "
                "Mount YOLO11 weights into /models or override the *_MODEL_PATH environment variables."
            )
        return YOLO(model_path)

    @staticmethod
    def _is_model_reference_usable(model_path: str) -> bool:
        path = Path(model_path)
        return path.exists() or (path.parent == Path(".") and path.name != "")

    def redact_image(self, raw_bytes: bytes) -> tuple[bytes, str, RedactionSummary]:
        image = self._decode_image(raw_bytes)
        face_boxes = self._detect_boxes(
            self.face_model,
            image,
            confidence=self.config.face_confidence,
        )
        plate_boxes = self._detect_boxes(
            self.license_plate_model,
            image,
            confidence=self.config.license_plate_confidence,
        )

        for box in [*face_boxes, *plate_boxes]:
            self._blur_region(image, box)

        encoded_image = self._encode_image(image)
        summary = RedactionSummary(faces=len(face_boxes), license_plates=len(plate_boxes))
        return encoded_image, "image/jpeg", summary

    @staticmethod
    def _decode_image(raw_bytes: bytes) -> np.ndarray:
        image_array = np.frombuffer(raw_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unsupported or corrupted image file")
        return image

    def _detect_boxes(self, model: YOLO, image: np.ndarray, confidence: float) -> list[tuple[int, int, int, int]]:
        results = model.predict(
            source=image,
            conf=confidence,
            device=self.config.device,
            verbose=False,
        )
        boxes = getattr(results[0], "boxes", None)
        if boxes is None or boxes.xyxy is None:
            return []

        detected_boxes: list[tuple[int, int, int, int]] = []
        for x1, y1, x2, y2 in boxes.xyxy.int().tolist():
            if x2 <= x1 or y2 <= y1:
                continue
            detected_boxes.append((x1, y1, x2, y2))
        return detected_boxes

    @staticmethod
    def _blur_region(image: np.ndarray, box: tuple[int, int, int, int]) -> None:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = box

        padding_x = max(4, int((x2 - x1) * 0.1))
        padding_y = max(4, int((y2 - y1) * 0.1))

        left = max(0, x1 - padding_x)
        top = max(0, y1 - padding_y)
        right = min(width, x2 + padding_x)
        bottom = min(height, y2 + padding_y)

        region = image[top:bottom, left:right]
        if region.size == 0:
            return

        kernel_size = max(15, (min(region.shape[0], region.shape[1]) // 3) | 1)
        image[top:bottom, left:right] = cv2.GaussianBlur(region, (kernel_size, kernel_size), sigmaX=0)

    @staticmethod
    def _encode_image(image: np.ndarray) -> bytes:
        success, encoded = cv2.imencode(".jpg", image)
        if not success:
            raise RuntimeError("Failed to encode redacted image")
        return encoded.tobytes()


def get_config() -> DetectorConfig:
    model_dir = Path(os.getenv("MODEL_DIR", "/models"))
    return DetectorConfig(
        face_model_path=os.getenv("FACE_MODEL_PATH", str(model_dir / "yolo11-face.pt")),
        license_plate_model_path=os.getenv(
            "LICENSE_PLATE_MODEL_PATH",
            str(model_dir / "yolo11-license-plate.pt"),
        ),
        device=os.getenv("YOLO_DEVICE", "cpu"),
        face_confidence=float(os.getenv("FACE_CONFIDENCE", "0.25")),
        license_plate_confidence=float(os.getenv("LICENSE_PLATE_CONFIDENCE", "0.25")),
    )


@lru_cache
def get_redaction_service() -> RedactionService:
    return RedactionService(get_config())
