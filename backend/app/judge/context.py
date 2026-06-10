"""JudgeContext — everything a judge sees for one agent-turn.

The triple (private monologue / public message / applied action+outcome) plus
ground truth (true balance/trust that turn, the ledger rows actually written),
so the judge can call a *lie* against facts, not just a tone shift.
``build_context`` is pure; the runner supplies the rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JudgeContext:
    session_id: str
    turn: int
    agent_id: str
    monologue: str
    public_message: str
    action: str
    arguments: dict
    outcome: str
    balance: float | None = None
    trust_score: float | None = None
    target_id: str | None = None
    transactions: list[dict] = field(default_factory=list)


def build_context(thought, snapshot, txns) -> JudgeContext:
    """*thought* = ThoughtLog, *snapshot* = TurnSnapshot | None,
    *txns* = this actor's Transaction rows for this turn."""
    tx_dicts = [
        {"action": t.action, "target_id": t.target_id, "delta": t.delta, "note": t.note}
        for t in txns
    ]
    target_id = next((t.target_id for t in txns if t.target_id), None)
    return JudgeContext(
        session_id=thought.session_id,
        turn=thought.turn,
        agent_id=thought.agent_id,
        monologue=thought.monologue or "",
        public_message=thought.public_message or "",
        action=thought.action,
        arguments=thought.arguments or {},
        outcome=thought.outcome or "",
        balance=snapshot.balance if snapshot is not None else None,
        trust_score=snapshot.trust_score if snapshot is not None else None,
        target_id=target_id,
        transactions=tx_dicts,
    )
