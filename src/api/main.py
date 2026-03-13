import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.core.database import engine
from src.api.routes import assessments, dashboard, prospects, scans, sites

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api.startup", environment=settings.environment)
    yield
    await engine.dispose()
    logger.info("api.shutdown")


app = FastAPI(
    title="EC-Scanner API",
    description="Experience Cloud Security Scanner — Salesforce guest user misconfiguration detector",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ───────────────────────────────────────────────────────────────────

app.include_router(sites.router, prefix="/api/v1/sites", tags=["sites"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["assessments"])
app.include_router(prospects.router, prefix="/api/v1/prospects", tags=["prospects"])
app.include_router(scans.router, prefix="/api/v1/scans", tags=["scans"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": "0.1.0",
    }
