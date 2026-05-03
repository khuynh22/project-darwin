from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    personality: Mapped[str] = mapped_column(String(2048), nullable=False)
    sprite: Mapped[str] = mapped_column(String(32), nullable=False)

    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    skip_next_turn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Social state
    spouse_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enemies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Error tracking for provider failures
    consecutive_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Position on the pixel map (set by frontend or default)
    pos_x: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pos_y: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    eliminated_at_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
