from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Response, status

from app.api.routes.runs import router as runs_router
from app.api.routes.support import router as support_router
from app.api.routes.tickets import router as tickets_router
from app.core.config import get_settings
from app.core.readiness import check_support_readiness
from app.models.api import HealthResponse, ReadinessResponse
from app.models.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    init_db(settings.sqlite_path, settings.sqlite_init_script)
    yield


app = FastAPI(
    title="Dify Internal Support Copilot",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(support_router, prefix=get_settings().api_prefix)
app.include_router(runs_router, prefix=get_settings().api_prefix)
app.include_router(tickets_router, prefix=get_settings().api_prefix)


@app.get("/healthz", response_model=HealthResponse, tags=["system"])
def healthz() -> HealthResponse:
    settings = get_settings()
    sqlite_accessible = _is_sqlite_accessible_read_only(settings.sqlite_path)
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        app_env=settings.app_env,
        check_type="liveness",
        sqlite_accessible=sqlite_accessible,
    )


@app.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    tags=["system"],
)
def readyz(response: Response) -> ReadinessResponse:
    readiness = check_support_readiness(get_settings())
    if not readiness.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        ready=readiness.ready,
        snapshot_version=readiness.snapshot_version,
        snapshot_count=readiness.snapshot_count,
        chunk_count=readiness.chunk_count,
        reasons=readiness.reasons,
    )


def _is_sqlite_accessible_read_only(sqlite_path: str) -> bool:
    target_path = Path(sqlite_path)
    if not target_path.exists():
        return False

    try:
        with sqlite3.connect(f"file:{target_path.as_posix()}?mode=ro", uri=True):
            return True
    except sqlite3.Error:
        return False
