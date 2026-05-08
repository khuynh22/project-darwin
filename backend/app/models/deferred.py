"""Deferred actions — investments and loans that mature after N turns."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DeferredAction(Base):
    __tablename__ = "deferred_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # "investment", "loan"
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    maturity_turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
