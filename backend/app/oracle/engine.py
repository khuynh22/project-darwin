"""The Oracle — turn loop, survival tax, bankruptcy, apex check.

Exposes a single coroutine `run_turn` that orchestrates one tick of the world,
plus `start_simulation` that initialises the roster and runs N turns. The
engine is provider-agnostic — it talks to agents through `app.agents.base.BaseAgent`.
"""
from __future__ import annotations

import asyncio
import logging
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


async def seed_roster(session: AsyncSession) -> None:
    settings = get_settings()
    existing = (await session.execute(select(Agent.agent_id))).scalars().all()
    have = set(existing)
    for spec in AGENT_ROSTER:
        if spec["agent_id"] in have:
            continue
        session.add(
            Agent(
                agent_id=spec["agent_id"],
                display_name=spec["display_name"],
                provider=spec["provider"],
                personality=spec["personality"],
                sprite=spec["sprite"],
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


async def run_turn(
    session: AsyncSession, *, turn: int, agents: dict[str, BaseAgent]
) -> TurnResult:
    """Execute one full turn for every alive agent, then apply tax if cycle boundary."""
    settings = get_settings()
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
        except Exception as exc:  # noqa: BLE001
            log.error("Agent %s decide() failed: %s", db_agent.agent_id, exc)
            decision = AgentDecision(action="work", arguments={},
                                     monologue=f"(API error -- falling back to work: {exc!s:.120})")
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
        if result.apex_declared:
            log.info("APEX declared: %s at turn %d", result.apex_declared, turn)
            break
        # gentle pacing for streaming clients
        await asyncio.sleep(0)
