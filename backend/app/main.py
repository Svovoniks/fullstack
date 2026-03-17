from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routes import router as jobs_router
from app.db import DatabaseError, ensure_default_admin_user, ensure_schema, get_user_by_id
from app.security import decode_access_token
from app.storage import StorageError, get_storage
from app.worker import JobWorker

app = FastAPI(
    title="Personal Data Redaction API",
    version="0.1.0",
    description="FastAPI backend for image/document redaction workflows.",
)

job_worker = JobWorker()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    protected_paths = ("/api/v1/jobs", "/api/v1/auth/me")
    if request.url.path.startswith(protected_paths):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = authorization.split(" ", maxsplit=1)[1]
        try:
            payload = decode_access_token(token)
        except ValueError as error:
            return JSONResponse(status_code=401, content={"detail": str(error)})

        user = get_user_by_id(str(payload["sub"]))
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "User not found"})

        request.state.current_user = user

    return await call_next(request)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "redaction-api", "status": "running"}


@app.on_event("startup")
def startup() -> None:
    ensure_schema()
    ensure_default_admin_user()
    get_storage().ensure_bucket()
    job_worker.start()


@app.on_event("shutdown")
def shutdown() -> None:
    job_worker.stop()


@app.exception_handler(DatabaseError)
def database_error_handler(_: Request, exc: DatabaseError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(StorageError)
def storage_error_handler(_: Request, exc: StorageError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else None
    message = first_error.get("msg", "Validation error") if first_error else "Validation error"
    return JSONResponse(status_code=422, content={"detail": message})


@app.exception_handler(HTTPException)
def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

app.include_router(jobs_router, prefix="/api/v1")
