from fastapi import APIRouter, HTTPException, status

from app.models.api import TicketRecord
from app.models.db import get_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/{ticket_id}", response_model=TicketRecord)
def read_ticket(ticket_id: str) -> TicketRecord:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' was not found.",
        )
    return ticket
