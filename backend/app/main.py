from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routes import router as jobs_router
from app.db import DatabaseError, init_db

app = FastAPI(
    title="Personal Data Redaction API",
    version="0.1.0",
    description="FastAPI backend for image/document redaction workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "redaction-api", "status": "running"}


@app.exception_handler(DatabaseError)
def database_error_handler(_: Request, exc: DatabaseError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else None
    message = first_error.get("msg", "Validation error") if first_error else "Validation error"
    return JSONResponse(status_code=422, content={"detail": message})


@app.exception_handler(HTTPException)
def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(jobs_router, prefix="/api/v1")
