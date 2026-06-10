"""SimSession — one isolated simulation tenant. Source of truth for the turn
counter and balance-visibility mode; everything else is scoped by ``session_id``."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SimSession(Base):
    """A single isolated simulation. Identified by a short URL-safe slug."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    current_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="fuzzy"
    )
    # RNG seed for this session's environment stochasticity (reproducibility).
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # "configuring" until a roster is set, then "ready".
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="configuring"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
