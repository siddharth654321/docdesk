# app/routers/tickets.py
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.schemas import Status, TicketCreate, TicketOut, TicketUpdate
from app.store import STORE as store

router = APIRouter(prefix="/tickets", tags=["tickets"])

MAX_PAGE_SIZE = get_settings().max_page_size
DEFAULT_PAGE_SIZE = min(20, MAX_PAGE_SIZE)  # the default must never exceed the cap


def _not_found(ticket_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(ticket: TicketCreate):
    return store.add(ticket)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: Status | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    tickets = store.all()
    if status is not None:
        tickets = [t for t in tickets if t["status"] == status]
    return tickets[offset : offset + limit]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int):
    ticket = store.get(ticket_id)
    if ticket is None:
        raise _not_found(ticket_id)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, changes: TicketUpdate):
    ticket = store.update(ticket_id, changes)
    if ticket is None:
        raise _not_found(ticket_id)
    return ticket
