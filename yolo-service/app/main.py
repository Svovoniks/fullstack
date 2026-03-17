from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app.redactor import get_config, get_redaction_service

app = FastAPI(
    title="YOLO11 Redaction Service",
    version="0.1.0",
    description="Accepts an image upload and returns the image with faces and license plates blurred.",
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "yolo11-redaction", "status": "running"}


@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    config = get_config()
    try:
        get_redaction_service()
    except RuntimeError as error:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "detail": str(error),
                "face_model_path": config.face_model_path,
                "license_plate_model_path": config.license_plate_model_path,
            },
        )

    return JSONResponse(
        content={
            "status": "ok",
            "face_model_path": config.face_model_path,
            "license_plate_model_path": config.license_plate_model_path,
            "device": config.device,
        }
    )


@app.post("/redact", tags=["redaction"])
async def redact_image(file: UploadFile = File(...)) -> Response:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    try:
        redacted_image, media_type, summary = get_redaction_service().redact_image(image_bytes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    headers = {
        "X-Faces-Blurred": str(summary.faces),
        "X-License-Plates-Blurred": str(summary.license_plates),
        "X-Redactions-Total": str(summary.total),
    }
    return Response(content=redacted_image, media_type=media_type, headers=headers)
