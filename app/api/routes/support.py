from fastapi import APIRouter, status

from app.models.api import Category, RunStatus, SupportAskRequest, SupportAskResponse
from app.models.db import insert_support_run

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/ask", response_model=SupportAskResponse, status_code=status.HTTP_202_ACCEPTED)
def ask_support(request: SupportAskRequest) -> SupportAskResponse:
    run = insert_support_run(
        question=request.question,
        request_payload=request.model_dump(mode="json"),
        category=Category.UNCLASSIFIED,
        confidence=0.0,
        status=RunStatus.SCAFFOLDED,
    )
    return SupportAskResponse(
        run=run,
        answer=None,
        citations=[],
        clarification=None,
        ticket=None,
        implemented_capabilities=[
            "request_validation",
            "sqlite_run_logging",
            "contract_scaffold",
        ],
        notes=[
            "Day 1 scaffold only: classification, retrieval, citation answer generation, clarification, and ticket creation are not implemented.",
            "The request has been recorded as a support run to keep the API contract testable.",
        ],
    )
