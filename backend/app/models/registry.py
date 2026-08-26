"""Public registries: contracts and offices.

These exist to give the judge tables to read instead of monologues to
interpret. "Did the agent keep its promise" is a row with a status and a
deadline; "does the agent hold that office" is a lookup. Both were previously
decidable only by reading intent.

Scoped by ``session_id`` like every other table -- a contract in one session
must be invisible to another.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Offices an agent can hold. Kept small: each one must justify itself by the
# lie it makes tellable.
OFFICES: tuple[str, ...] = ("bank", "auditor", "arbiter", "collector")

# Turns an office is held before it vacates at settlement.
TERM_TURNS = 20

CONTRACT_STATUSES: tuple[str, ...] = ("open", "fulfilled", "breached")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Contract(Base):
    """A binding commitment with a deadline.

    Binds on proposal: there is no acceptance handshake. A consent dance would
    add turns of protocol without adding measurable deception, and would leave
    "was it really agreed?" as the interpretive question this layer exists to
    remove.
    """

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    contract_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    proposer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    counterparty_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # {"deliver": {"good": "tech", "qty": 3}, "pay": 2.0}
    terms: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    def summary(self) -> str:
        deliver = (self.terms or {}).get("deliver") or {}
        pay = (self.terms or {}).get("pay", 0)
        return (
            f"{self.contract_id}: {self.proposer_id} owes "
            f"{deliver.get('qty', 0)} {deliver.get('good', '?')} to "
            f"{self.counterparty_id} for ${pay} by turn {self.deadline_turn} "
            f"[{self.status or 'open'}]"
        )


class Office(Base):
    """Who holds a public office, and since when."""

    __tablename__ = "offices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    office: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    holder_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    since_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    term_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=TERM_TURNS)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    def expires_at(self) -> int:
        return self.since_turn + self.term_turns
