"""The Oracle — turn loop, survival tax, bankruptcy, apex check.

Exposes a single coroutine `run_turn` that orchestrates one tick of the world,
plus `start_simulation` that initialises the roster and runs N turns. The
engine is provider-agnostic — it talks to agents through `app.agents.base.BaseAgent`.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentDecision, BaseAgent
from app.config import AGENT_ROSTER, get_settings
from app.db import SessionLocal, init_db
from app.models.agent import Agent
from app.models.ledger import ThoughtLog, Transaction, WorldEvent
from app.oracle.actions import ACTION_TABLE
from app.oracle.schemas import ARG_MODELS

log = logging.getLogger(__name__)


@dataclass
class TurnResult:
    turn: int
    apex_declared: str | None
    eliminated: list[str]
    paused: bool = False
    pause_reason: str | None = None
    pause_agent_id: str | None = None


def _is_permanent_error(exc: Exception) -> bool:
    """Check if an exception represents a permanent provider failure (auth, not found)."""
    exc_type = type(exc).__name__
    permanent_types = ("AuthenticationError", "PermissionDenied", "NotFoundError")
    if exc_type in permanent_types:
        return True
    msg = str(exc).lower()
    for code in ("401", "403", "404", "invalid api key", "authentication", "permission denied"):
        if code in msg:
            return True
    return False


async def seed_roster(session: AsyncSession, roster: list[dict] | None = None) -> None:
    settings = get_settings()
    specs = roster or AGENT_ROSTER
    existing = (await session.execute(select(Agent.agent_id))).scalars().all()
    have = set(existing)
    for spec in specs:
        if spec["agent_id"] in have:
            continue
        session.add(
            Agent(
                agent_id=spec["agent_id"],
                display_name=spec["display_name"],
                provider=spec["provider"],
                personality=spec.get("personality", "Adaptive agent."),
                sprite=spec.get("sprite", "robot"),
                balance=settings.starting_capital,
                alive=True,
                allies=[],
                enemies=[],
            )
        )
    await session.commit()


async def _world_state(session: AsyncSession, turn: int) -> dict:
    rows = (await session.execute(select(Agent))).scalars().all()
    return {
        "turn": turn,
        "agents": [
            {
                "agent_id": a.agent_id,
                "display_name": a.display_name,
                "balance": a.balance,
                "alive": a.alive,
                "spouse": a.spouse_id,
                "allies": list(a.allies or []),
                "enemies": list(a.enemies or []),
                "skip_next_turn": a.skip_next_turn,
            }
            for a in rows
        ],
    }


async def _apply_decision(
    session: AsyncSession, *, turn: int, agent: Agent, decision: AgentDecision
) -> str:
    handler = ACTION_TABLE.get(decision.action)
    if handler is None:
        return f"invalid action: {decision.action}"
    arg_model = ARG_MODELS[decision.action]
    try:
        validated = arg_model.model_validate(decision.arguments).model_dump()
    except Exception as e:  # noqa: BLE001
        return f"argument validation failed: {e}"
    result = await handler(session, turn=turn, actor_id=agent.agent_id, **validated)
    return result.note + (" [ok]" if result.success else " [rejected]")


async def _apply_survival_tax(session: AsyncSession, turn: int) -> list[str]:
    settings = get_settings()
    eliminated: list[str] = []
    rows = (await session.execute(select(Agent).where(Agent.alive.is_(True)))).scalars().all()
    for a in rows:
        a.balance = round(a.balance - settings.survival_tax, 2)
        session.add(
            Transaction(
                turn=turn, actor_id=a.agent_id, target_id=None, action="tax",
                delta=-settings.survival_tax, payload={}, note="survival tax",
            )
        )
        if a.balance <= 0:
            a.alive = False
            a.eliminated_at_turn = turn
            eliminated.append(a.agent_id)
            session.add(WorldEvent(turn=turn, kind="bankruptcy", payload={"agent_id": a.agent_id}))
    return eliminated


def _apex_holder(agents: list[Agent], threshold: float) -> str | None:
    alive = [a for a in agents if a.alive]
    if len(alive) <= 1:
        return alive[0].agent_id if alive else None
    total = sum(a.balance for a in alive)
    if total <= 0:
        return None
    for a in alive:
        if a.balance / total >= threshold:
            return a.agent_id
    return None


async def _process_deferred(session: AsyncSession, turn: int) -> None:
    """Settle investments and loans that mature this turn."""
    from app.models.deferred import DeferredAction

    rows = (await session.execute(
        select(DeferredAction).where(
            DeferredAction.maturity_turn == turn,
            DeferredAction.resolved.is_(False),
        )
    )).scalars().all()

    for d in rows:
        d.resolved = True
        if d.kind == "investment":
            actor = (await session.execute(
                select(Agent).where(Agent.agent_id == d.actor_id)
            )).scalar_one_or_none()
            if actor is None or not actor.alive:
                continue
            success = random.random() < 0.70
            if success:
                ret = round(d.amount * random.uniform(1.2, 2.0), 2)
                actor.balance = round(actor.balance + ret, 2)
                session.add(Transaction(
                    turn=turn, actor_id=d.actor_id, target_id=None, action="invest_return",
                    delta=ret, payload={"original": d.amount, "return": ret},
                    note=f"investment matured: +${ret:.2f}",
                ))
            else:
                session.add(Transaction(
                    turn=turn, actor_id=d.actor_id, target_id=None, action="invest_loss",
                    delta=0.0, payload={"original": d.amount},
                    note=f"investment failed: lost ${d.amount:.2f}",
                ))

        elif d.kind == "loan":
            creditor = (await session.execute(
                select(Agent).where(Agent.agent_id == d.actor_id)
            )).scalar_one_or_none()
            debtor = (await session.execute(
                select(Agent).where(Agent.agent_id == d.target_id)
            )).scalar_one_or_none()
            repayment = d.payload.get("repayment", round(d.amount * 1.3, 2))
            if debtor and debtor.alive and debtor.balance >= repayment:
                debtor.balance = round(debtor.balance - repayment, 2)
                if creditor and creditor.alive:
                    creditor.balance = round(creditor.balance + repayment, 2)
                session.add(Transaction(
                    turn=turn, actor_id=d.target_id, target_id=d.actor_id, action="loan_repay",
                    delta=-repayment, payload={"original": d.amount, "repayment": repayment},
                    note=f"loan repaid: ${repayment:.2f} to {d.actor_id}",
                ))
            else:
                # Debtor defaulted
                session.add(Transaction(
                    turn=turn, actor_id=d.actor_id, target_id=d.target_id, action="loan_default",
                    delta=0.0, payload={"original": d.amount, "repayment": repayment},
                    note=f"loan defaulted by {d.target_id}",
                ))


async def run_turn(
    session: AsyncSession, *, turn: int, agents: dict[str, BaseAgent]
) -> TurnResult:
    """Execute one full turn for every alive agent, then apply tax if cycle boundary."""
    settings = get_settings()

    # Settle maturing investments and loans before agent decisions
    await _process_deferred(session, turn)

    db_agents = (await session.execute(select(Agent))).scalars().all()
    state = await _world_state(session, turn)

    for db_agent in db_agents:
        if not db_agent.alive:
            continue
        if db_agent.skip_next_turn:
            db_agent.skip_next_turn = False
            session.add(
                ThoughtLog(turn=turn, agent_id=db_agent.agent_id, monologue="(sabotaged — turn skipped)",
                           action="skip", arguments={}, outcome="skipped")
            )
            continue

        client = agents[db_agent.agent_id]
        try:
            decision = await client.decide(state, db_agent)
            # Reset error counter on success
            db_agent.consecutive_errors = 0
            db_agent.last_error = None
        except Exception as exc:  # noqa: BLE001
            log.error("Agent %s decide() failed: %s", db_agent.agent_id, exc)
            db_agent.consecutive_errors += 1
            db_agent.last_error = str(exc)[:512]
            permanent = _is_permanent_error(exc)

            if permanent or db_agent.consecutive_errors >= settings.error_threshold:
                reason = (
                    f"permanent error: {exc!s:.200}" if permanent
                    else f"{db_agent.consecutive_errors} consecutive failures: {exc!s:.200}"
                )
                session.add(
                    ThoughtLog(
                        turn=turn, agent_id=db_agent.agent_id,
                        monologue=f"(Provider failure -- simulation paused: {reason})",
                        action="skip", arguments={}, outcome="paused",
                    )
                )
                session.add(WorldEvent(turn=turn, kind="provider_failure", payload={
                    "agent_id": db_agent.agent_id, "error": str(exc)[:200],
                    "consecutive_errors": db_agent.consecutive_errors, "permanent": permanent,
                }))
                await session.commit()
                return TurnResult(
                    turn=turn, apex_declared=None, eliminated=[],
                    paused=True, pause_reason=reason, pause_agent_id=db_agent.agent_id,
                )

            # Under threshold: fall back to work but log the warning
            decision = AgentDecision(
                action="work", arguments={},
                monologue=f"(API error #{db_agent.consecutive_errors} -- falling back to work: {exc!s:.120})",
            )

        outcome = await _apply_decision(session, turn=turn, agent=db_agent, decision=decision)
        session.add(
            ThoughtLog(
                turn=turn,
                agent_id=db_agent.agent_id,
                monologue=decision.monologue,
                action=decision.action,
                arguments=decision.arguments,
                outcome=outcome,
            )
        )
        # Stream to JSONL file if exporter is active
        from app.thought_export import get_exporter  # local import avoids cycle
        exporter = get_exporter()
        if exporter is not None:
            exporter.append(
                turn=turn, agent_id=db_agent.agent_id,
                monologue=decision.monologue, action=decision.action,
                arguments=decision.arguments, outcome=outcome,
            )

    eliminated: list[str] = []
    if turn > 0 and turn % settings.tax_interval_turns == 0:
        eliminated = await _apply_survival_tax(session, turn)

    refreshed = (await session.execute(select(Agent))).scalars().all()
    apex = _apex_holder(refreshed, settings.apex_wealth_fraction)
    if apex:
        session.add(WorldEvent(turn=turn, kind="apex", payload={"agent_id": apex}))

    await session.commit()
    return TurnResult(turn=turn, apex_declared=apex, eliminated=eliminated)


async def start_simulation(
    *,
    max_turns: int | None = None,
    on_turn=None,
) -> None:
    """Initialise the DB + roster + agent clients, then run the turn loop."""
    from app.agents.factory import build_agents  # local import avoids cycle

    settings = get_settings()
    target_turns = max_turns or settings.max_turns

    await init_db()
    async with SessionLocal() as session:
        await seed_roster(session)

    agents = build_agents()

    for turn in range(1, target_turns + 1):
        async with SessionLocal() as session:
            result = await run_turn(session, turn=turn, agents=agents)
        if on_turn:
            await on_turn(result)
        if result.paused:
            log.warning("Simulation PAUSED at turn %d: %s", turn, result.pause_reason)
            break
        if result.apex_declared:
            log.info("APEX declared: %s at turn %d", result.apex_declared, turn)
            break
        # gentle pacing for streaming clients
        await asyncio.sleep(0)
