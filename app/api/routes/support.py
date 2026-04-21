from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.readiness import SupportReadinessError
from app.models.api import SupportAskRequest, SupportAskResponse
from app.support.service import handle_support_request

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/ask", response_model=SupportAskResponse, status_code=status.HTTP_200_OK)
def ask_support(request: SupportAskRequest) -> SupportAskResponse:
    try:
        return handle_support_request(request=request, settings=get_settings())
    except SupportReadinessError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
