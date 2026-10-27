from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import assessments, auth, consultations, patients, safety


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Patient-specific follow-up, PHQ-9, history, and clinician review API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(patients.router, prefix="/api")
app.include_router(consultations.router, prefix="/api")
app.include_router(assessments.router, prefix="/api")
app.include_router(safety.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "groq": "configured" if settings.groq_api_key else "missing_key",
    }