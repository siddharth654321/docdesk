# app/store.py
from datetime import datetime, timezone
from itertools import count

from app.schemas import Status, TicketCreate, TicketUpdate


class TicketStore:
    """In-memory ticket storage backed by a dict. Replaced by a database later."""

    def __init__(self) -> None:
        self._items: dict[int, dict] = {}
        self._ids = count(1)

    def add(self, data: TicketCreate) -> dict:
        # Server-owned fields go last so they always win over client data.
        ticket = {
            **data.model_dump(),
            "id": next(self._ids),
            "status": Status.open,
            "created_at": datetime.now(timezone.utc),
        }
        self._items[ticket["id"]] = ticket
        return ticket

    def get(self, ticket_id: int) -> dict | None:
        return self._items.get(ticket_id)

    def all(self) -> list[dict]:
        return list(self._items.values())

    def update(self, ticket_id: int, data: TicketUpdate) -> dict | None:
        ticket = self._items.get(ticket_id)
        if ticket is None:
            return None
        # exclude_unset: only fields the client actually sent are applied.
        ticket.update(data.model_dump(exclude_unset=True))
        return ticket


STORE = TicketStore()
