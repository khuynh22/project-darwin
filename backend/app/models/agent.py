"""Agent model representing an autonomous entity in the simulation, with attributes for identity,
social relationships, trust, inventory, and status effects."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    """Represents an autonomous agent in the simulation."""

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
    marriage_pending: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # agent who proposed
    allies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enemies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Trust & reputation
    trust_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=50.0, server_default="50.0"
    )
    steal_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    share_balance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    # Goods economy
    specialty: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ore", server_default="ore"
    )
    inventory: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=lambda: {"ore": 0, "food": 0, "tech": 0}
    )

    # Status effects
    rest_bonus: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    will_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extortion_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bribe_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Error tracking for provider failures
    consecutive_errors: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    eliminated_at_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
