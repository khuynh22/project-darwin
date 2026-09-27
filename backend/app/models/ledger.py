from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Transaction(Base):
    """Append-only ledger of every economic event in the simulation."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, default="cli"
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class ThoughtLog(Base):
    """Private monologue + public action chosen by an agent on a given turn."""

    __tablename__ = "thoughts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, default="cli"
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    monologue: Mapped[str] = mapped_column(String(8192), nullable=False, default="")
    public_message: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", server_default=""
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    outcome: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class TurnSnapshot(Base):
    """Per-turn snapshot of each agent's state. Enables longitudinal metrics
    (wealth/trust trajectories, Gini-over-time) that the delta ledger cannot
    reconstruct -- marriage/divorce pool/split balances with a ``delta=0`` row."""

    __tablename__ = "turn_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, default="cli"
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    inventory: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    spouse_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Everything below affects either an action's outcome distribution or what
    # render_world_brief shows the model. Restoring a turn without them
    # fabricates a different situation: steal_count alone moves steal success
    # from ~20% back to 60%.
    steal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    food_buffer: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, default="plaza")
    allies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    enemies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skip_next_turn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rest_bonus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    share_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    will_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marriage_pending: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extortion_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bribe_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class WorldEvent(Base):
    """High-level events: cycle tax, bankruptcy, marriage, apex declared, etc."""

    __tablename__ = "world_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, default="cli"
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
