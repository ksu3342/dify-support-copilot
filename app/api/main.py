from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.routes.runs import router as runs_router
from app.api.routes.support import router as support_router
from app.api.routes.tickets import router as tickets_router
from app.core.config import get_settings
from app.models.api import HealthResponse
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
    db_ready = Path(settings.sqlite_path).exists()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        app_env=settings.app_env,
        sqlite_ready=db_ready,
    )
