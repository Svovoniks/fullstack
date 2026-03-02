from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as jobs_router

app = FastAPI(
    title="Personal Data Redaction API",
    version="0.1.0",
    description="FastAPI backend for image/document redaction workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "redaction-api", "status": "running"}


app.include_router(jobs_router, prefix="/api/v1")
