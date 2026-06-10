"""DeceptionJudgment — cached LLM-judge verdicts over the per-agent-turn triple.

One row = one judge sample for one agent-turn. Identity is the tuple
(session_id, turn, agent_id, judge_model, prompt_version, sample_idx) so
multiple judge models, prompt revisions, and K reliability samples coexist.
Judge labels are a *measurement* (reliability is reported), not a
deterministic metric — see the Phase 2 design spec.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DeceptionJudgment(Base):
    __tablename__ = "deception_judgments"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "turn", "agent_id",
            "judge_model", "prompt_version", "sample_idx",
            name="uq_judgment_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, default="cli"
    )
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    judge_model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    sample_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deceptive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deception_type: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    channels_in_conflict: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rationale: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
