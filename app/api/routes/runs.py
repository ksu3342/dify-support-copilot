from fastapi import APIRouter, HTTPException, status

from app.models.api import RunRecord
from app.models.db import get_support_run

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunRecord)
def read_run(run_id: str) -> RunRecord:
    run = get_support_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' was not found.",
        )
    return run
