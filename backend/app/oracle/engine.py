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
    for code in (
        "401",
        "403",
        "404",
        "invalid api key",
        "authentication",
        "permission denied",
    ):
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
                sprite=spec.get("sprite", "blue"),
                specialty=random.choice(["ore", "food", "tech"]),
                balance=settings.starting_capital,
                alive=True,
                allies=[],
                enemies=[],
            )
        )
    await session.commit()


async def _get_agent_by_id(session: AsyncSession, agent_id: str) -> Agent | None:
    return (
        await session.execute(select(Agent).where(Agent.agent_id == agent_id))
    ).scalar_one_or_none()


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
                "trust_score": a.trust_score,
                "steal_count": a.steal_count,
                "share_balance": a.share_balance,
                "inventory": a.inventory or {},
                "specialty": a.specialty,
                "rest_bonus": a.rest_bonus,
                "will_target": a.will_target,
                "extortion_pending": a.extortion_pending,
                "bribe_pending": a.bribe_pending,
            }
            for a in rows
        ],
    }


async def _agent_history(
    session: AsyncSession, agent_id: str, limit: int = 10
) -> list[dict]:
    """Fetch recent thought history for an agent (most recent first)."""
    rows = (
        (
            await session.execute(
                select(ThoughtLog)
                .where(ThoughtLog.agent_id == agent_id, ThoughtLog.action != "skip")
                .order_by(ThoughtLog.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "turn": t.turn,
            "action": t.action,
            "args": ", ".join(f"{k}={v}" for k, v in (t.arguments or {}).items()),
            "outcome": t.outcome,
        }
        for t in rows
    ]


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
    validated.pop(
        "reasoning", None
    )  # reasoning is for monologue, not the action handler
    validated.pop(
        "public_message", None
    )  # public_message stored separately on ThoughtLog
    result = await handler(session, turn=turn, actor_id=agent.agent_id, **validated)
    return result.note + (" [ok]" if result.success else " [rejected]")


def _compute_tax(cash: float) -> float:
    """Progressive tax brackets on cash holdings (not invested capital)."""
    if cash <= 2.0:
        return 0.0
    tax = 0.0
    # $2-5: 5%
    bracket = min(cash, 5.0) - 2.0
    if bracket > 0:
        tax += bracket * 0.05
    # $5-10: 10%
    bracket = min(cash, 10.0) - 5.0
    if bracket > 0:
        tax += bracket * 0.10
    # $10-20: 15%
    bracket = min(cash, 20.0) - 10.0
    if bracket > 0:
        tax += bracket * 0.15
    # $20+: 20%
    if cash > 20.0:
        tax += (cash - 20.0) * 0.20
    return round(tax, 2)


async def _apply_survival_tax(session: AsyncSession, turn: int) -> list[str]:
    from app.models.deferred import DeferredAction

    eliminated: list[str] = []

    # Check for active strikes -- if 3+ agents struck this turn, tax is waived
    strike_count = 0
    thoughts = (
        (
            await session.execute(
                select(ThoughtLog).where(
                    ThoughtLog.turn == turn, ThoughtLog.action == "strike"
                )
            )
        )
        .scalars()
        .all()
    )
    strike_count = len(thoughts)
    if strike_count >= 3:
        session.add(
            WorldEvent(
                turn=turn,
                kind="strike_success",
                payload={
                    "strikers": strike_count,
                    "note": "tax waived by collective strike",
                },
            )
        )
        return eliminated

    rows = (
        (await session.execute(select(Agent).where(Agent.alive.is_(True))))
        .scalars()
        .all()
    )
    for a in rows:
        # Calculate locked capital (investments + outstanding loans given)
        locked = (
            (
                await session.execute(
                    select(DeferredAction).where(
                        DeferredAction.actor_id == a.agent_id,
                        DeferredAction.resolved.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        locked_amount = sum(d.amount for d in locked)
        inv = dict(a.inventory or {"ore": 0, "food": 0, "tech": 0})

        # Food consumption: eat 1 food or pay $1 hunger penalty
        hunger_penalty = 0.0
        if inv.get("food", 0) >= 1:
            inv["food"] = inv["food"] - 1
            a.inventory = inv
        else:
            hunger_penalty = 1.00

        # Compute progressive tax on cash (minus locked capital)
        taxable_cash = max(0.0, a.balance - locked_amount)
        tax = _compute_tax(taxable_cash)

        total_cost = round(tax + hunger_penalty, 2)
        if total_cost <= 0:
            continue
        a.balance = round(a.balance - total_cost, 2)

        parts = []
        if tax > 0:
            parts.append(f"tax ${tax:.2f}")
        if hunger_penalty > 0:
            parts.append(f"hunger ${hunger_penalty:.2f}")
        session.add(
            Transaction(
                turn=turn,
                actor_id=a.agent_id,
                target_id=None,
                action="tax",
                delta=-total_cost,
                payload={
                    "taxable_cash": taxable_cash,
                    "locked": locked_amount,
                    "hunger": hunger_penalty,
                },
                note=" + ".join(parts) + f" (cash ${taxable_cash:.2f})",
            )
        )
        if a.balance <= 0:
            # Calculate pre-death estate (balance before this tax wiped them)
            estate = round(max(a.balance + total_cost, 0), 2)
            await _eliminate_agent(session, a, turn=turn, estate=estate)
            eliminated.append(a.agent_id)
    return eliminated


async def _eliminate_agent(
    session: AsyncSession,
    agent: Agent,
    *,
    turn: int,
    estate: float,
) -> None:
    """Mark an agent eliminated, pass any estate + inventory to heir, log it.

    `estate` is the pre-death liquid balance available for inheritance.
    Pure bankruptcies (instant $0 elimination outside the tax sweep) pass
    estate=0 — only inventory transfers in that case.
    """
    agent.alive = False
    agent.eliminated_at_turn = turn
    agent.balance = 0.0

    heir_id = agent.will_target or agent.spouse_id
    if heir_id and estate > 0:
        heir = await _get_agent_by_id(session, heir_id)
        if heir and heir.alive:
            # Will = 50% of estate, spouse = 100% of estate
            pct = 0.5 if agent.will_target and agent.will_target == heir_id else 1.0
            inheritance = round(estate * pct, 2)
            heir.balance = round(heir.balance + inheritance, 2)
            via = "will" if agent.will_target == heir_id else "spouse"
            session.add(
                Transaction(
                    turn=turn,
                    actor_id=agent.agent_id,
                    target_id=heir_id,
                    action="inherit",
                    delta=inheritance,
                    payload={"via": via, "estate": estate},
                    note=f"${inheritance:.2f} inherited by {heir_id} ({via})",
                )
            )

    if heir_id and agent.inventory:
        heir2 = await _get_agent_by_id(session, heir_id)
        if heir2 and heir2.alive:
            h_inv = dict(heir2.inventory or {"ore": 0, "food": 0, "tech": 0})
            for g, qty in (agent.inventory or {}).items():
                h_inv[g] = h_inv.get(g, 0) + qty
            heir2.inventory = h_inv
        agent.inventory = {"ore": 0, "food": 0, "tech": 0}

    session.add(
        WorldEvent(
            turn=turn,
            kind="bankruptcy",
            payload={"agent_id": agent.agent_id, "heir": heir_id, "estate": estate},
        )
    )


async def _check_bankruptcies(session: AsyncSession, turn: int) -> list[str]:
    """Eliminate any alive agent that has run out of cash.

    Runs every turn -- a $0 balance is fatal even outside the tax sweep,
    regardless of invested capital or inventory holdings.
    """
    rows = (
        (await session.execute(select(Agent).where(Agent.alive.is_(True))))
        .scalars()
        .all()
    )
    eliminated: list[str] = []
    for a in rows:
        if a.balance <= 0:
            await _eliminate_agent(session, a, turn=turn, estate=0.0)
            eliminated.append(a.agent_id)
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

    rows = (
        (
            await session.execute(
                select(DeferredAction).where(
                    DeferredAction.maturity_turn == turn,
                    DeferredAction.resolved.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )

    for d in rows:
        d.resolved = True
        if d.kind == "investment":
            actor = (
                await session.execute(select(Agent).where(Agent.agent_id == d.actor_id))
            ).scalar_one_or_none()
            if actor is None or not actor.alive:
                continue
            success = random.random() < 0.70
            if success:
                ret = round(d.amount * random.uniform(1.2, 2.0), 2)
                actor.balance = round(actor.balance + ret, 2)
                session.add(
                    Transaction(
                        turn=turn,
                        actor_id=d.actor_id,
                        target_id=None,
                        action="invest_return",
                        delta=ret,
                        payload={"original": d.amount, "return": ret},
                        note=f"investment matured: +${ret:.2f}",
                    )
                )
            else:
                session.add(
                    Transaction(
                        turn=turn,
                        actor_id=d.actor_id,
                        target_id=None,
                        action="invest_loss",
                        delta=0.0,
                        payload={"original": d.amount},
                        note=f"investment failed: lost ${d.amount:.2f}",
                    )
                )

        elif d.kind == "loan":
            creditor = (
                await session.execute(select(Agent).where(Agent.agent_id == d.actor_id))
            ).scalar_one_or_none()
            debtor = (
                await session.execute(
                    select(Agent).where(Agent.agent_id == d.target_id)
                )
            ).scalar_one_or_none()
            repayment = d.payload.get("repayment", round(d.amount * 1.3, 2))
            if debtor and debtor.alive and debtor.balance >= repayment:
                debtor.balance = round(debtor.balance - repayment, 2)
                if creditor and creditor.alive:
                    creditor.balance = round(creditor.balance + repayment, 2)
                session.add(
                    Transaction(
                        turn=turn,
                        actor_id=d.target_id,
                        target_id=d.actor_id,
                        action="loan_repay",
                        delta=-repayment,
                        payload={"original": d.amount, "repayment": repayment},
                        note=f"loan repaid: ${repayment:.2f} to {d.actor_id}",
                    )
                )
            else:
                # Debtor defaulted -- trust penalty
                if debtor and debtor.alive:
                    debtor.trust_score = max(0, debtor.trust_score - 10)
                session.add(
                    Transaction(
                        turn=turn,
                        actor_id=d.actor_id,
                        target_id=d.target_id,
                        action="loan_default",
                        delta=0.0,
                        payload={"original": d.amount, "repayment": repayment},
                        note=f"loan defaulted by {d.target_id}",
                    )
                )

    # Process extortion threats (auto-sabotage if not paid)
    extorted = (
        (
            await session.execute(
                select(Agent).where(
                    Agent.extortion_pending.isnot(None), Agent.alive.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    for target_agent in extorted:
        ext = target_agent.extortion_pending
        if not ext or ext.get("turn", 0) >= turn:
            continue  # give them one turn to respond
        extorter_id = ext.get("from")
        # Check if target paid (gifted/traded to extorter since the demand)
        paid = (
            (
                await session.execute(
                    select(Transaction).where(
                        Transaction.actor_id == target_agent.agent_id,
                        Transaction.target_id == extorter_id,
                        Transaction.turn > ext.get("turn", 0),
                        Transaction.delta < 0,
                    )
                )
            )
            .scalars()
            .first()
        )
        if not paid:
            # Auto-trigger threat
            threat = ext.get("threat", "sabotage")
            if threat == "sabotage":
                target_agent.skip_next_turn = True
                session.add(
                    Transaction(
                        turn=turn,
                        actor_id=extorter_id,
                        target_id=target_agent.agent_id,
                        action="extort_trigger",
                        delta=0,
                        payload=ext,
                        note=f"extortion enforced: {target_agent.agent_id} sabotaged",
                    )
                )
            elif threat == "slander":
                target_agent.trust_score = max(0, target_agent.trust_score - 8)
                session.add(
                    Transaction(
                        turn=turn,
                        actor_id=extorter_id,
                        target_id=target_agent.agent_id,
                        action="extort_trigger",
                        delta=0,
                        payload=ext,
                        note=f"extortion enforced: {target_agent.agent_id} slandered",
                    )
                )
        target_agent.extortion_pending = None


async def _decide_one(
    client: BaseAgent,
    state: dict,
    db_agent: Agent,
    history: list[dict],
    gaslights: list[str] | None = None,
) -> AgentDecision:
    """Call decide() for one agent with its own history + gaslight injections."""
    agent_state = {**state, "_history": history, "_gaslights": gaslights or []}
    return await asyncio.wait_for(client.decide(agent_state, db_agent), timeout=120)


async def run_turn(
    session: AsyncSession,
    *,
    turn: int,
    agents: dict[str, BaseAgent],
    balance_visibility: str = "fuzzy",
) -> TurnResult:
    """Execute one full turn for every alive agent, then apply tax if cycle boundary.

    All agent decide() calls run in **parallel** -- total turn time is the
    slowest agent, not the sum of all agents.  Decisions are then applied
    sequentially to avoid DB race conditions.
    """
    settings = get_settings()

    # Settle maturing investments and loans before agent decisions
    await _process_deferred(session, turn)

    db_agents = (await session.execute(select(Agent))).scalars().all()
    state = await _world_state(session, turn)
    state["_balance_visibility"] = balance_visibility

    # Phase 1: Handle skipped agents, collect active agents for parallel decide
    active: list[Agent] = []
    for db_agent in db_agents:
        if not db_agent.alive:
            continue
        if db_agent.skip_next_turn:
            db_agent.skip_next_turn = False
            session.add(
                ThoughtLog(
                    turn=turn,
                    agent_id=db_agent.agent_id,
                    monologue="(sabotaged -- turn skipped)",
                    action="skip",
                    arguments={},
                    outcome="skipped",
                )
            )
            continue
        active.append(db_agent)

    # Phase 2: Fetch histories + gaslight events, then fire decide() in parallel
    histories: dict[str, list[dict]] = {}
    gaslights: dict[str, list[str]] = {}
    for db_agent in active:
        histories[db_agent.agent_id] = await _agent_history(session, db_agent.agent_id)
        # Fetch gaslight events targeting this agent from recent turns
        gl_rows = (
            (
                await session.execute(
                    select(WorldEvent).where(
                        WorldEvent.kind == "gaslight",
                        WorldEvent.turn >= max(1, turn - 3),
                    )
                )
            )
            .scalars()
            .all()
        )
        gaslights[db_agent.agent_id] = [
            e.payload.get("fake_event", "")
            for e in gl_rows
            if e.payload.get("target") == db_agent.agent_id
        ]

    tasks = {
        db_agent.agent_id: asyncio.create_task(
            _decide_one(
                agents[db_agent.agent_id],
                state,
                db_agent,
                histories[db_agent.agent_id],
                gaslights.get(db_agent.agent_id, []),
            )
        )
        for db_agent in active
    }

    # Wait for ALL agents to finish (or fail)
    results: dict[str, AgentDecision | Exception] = {}
    done = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for agent_id, result in zip(tasks.keys(), done, strict=True):
        results[agent_id] = result

    # Phase 3: Apply decisions sequentially (DB writes must be serial)
    from app.thought_export import get_exporter

    exporter = get_exporter()

    for db_agent in active:
        result = results[db_agent.agent_id]

        if isinstance(result, Exception):
            exc = result
            if isinstance(exc, TimeoutError):
                exc = TimeoutError("timed out after 120s")
            log.error("Agent %s decide() failed: %r", db_agent.agent_id, exc)
            db_agent.consecutive_errors += 1
            db_agent.last_error = str(exc)[:512]
            permanent = _is_permanent_error(exc)

            if permanent or db_agent.consecutive_errors >= settings.error_threshold:
                reason = (
                    f"permanent error: {exc!s:.200}"
                    if permanent
                    else f"{db_agent.consecutive_errors} consecutive failures: {exc!s:.200}"
                )
                session.add(
                    ThoughtLog(
                        turn=turn,
                        agent_id=db_agent.agent_id,
                        monologue=f"(Provider failure -- simulation paused: {reason})",
                        action="skip",
                        arguments={},
                        outcome="paused",
                    )
                )
                session.add(
                    WorldEvent(
                        turn=turn,
                        kind="provider_failure",
                        payload={
                            "agent_id": db_agent.agent_id,
                            "error": str(exc)[:200],
                            "consecutive_errors": db_agent.consecutive_errors,
                            "permanent": permanent,
                        },
                    )
                )
                await session.commit()
                return TurnResult(
                    turn=turn,
                    apex_declared=None,
                    eliminated=[],
                    paused=True,
                    pause_reason=reason,
                    pause_agent_id=db_agent.agent_id,
                )

            decision = AgentDecision(
                action="work",
                arguments={},
                monologue=f"(API error #{db_agent.consecutive_errors} -- falling back to work: {exc!s:.120})",
            )
        else:
            decision = result
            db_agent.consecutive_errors = 0
            db_agent.last_error = None

        # Apply major action
        outcome = await _apply_decision(
            session, turn=turn, agent=db_agent, decision=decision
        )
        public_msg = (
            decision.arguments.pop("public_message", "")
            if isinstance(decision.arguments, dict)
            else ""
        )

        # Apply optional free action (if provided and valid)
        free_outcome = ""
        if decision.free_action:
            from app.oracle.schemas import FREE_ACTIONS

            if decision.free_action in FREE_ACTIONS:
                free_decision = AgentDecision(
                    action=decision.free_action,
                    arguments=decision.free_arguments,
                )
                free_outcome = await _apply_decision(
                    session, turn=turn, agent=db_agent, decision=free_decision
                )
                free_outcome = f" | free: {decision.free_action} -> {free_outcome}"
            else:
                free_outcome = (
                    f" | free: {decision.free_action} rejected (not a free action)"
                )

        session.add(
            ThoughtLog(
                turn=turn,
                agent_id=db_agent.agent_id,
                monologue=decision.monologue,
                public_message=public_msg or "",
                action=decision.action,
                arguments=decision.arguments,
                outcome=outcome + free_outcome,
            )
        )
        if exporter is not None:
            exporter.append(
                turn=turn,
                agent_id=db_agent.agent_id,
                monologue=decision.monologue,
                action=decision.action,
                arguments=decision.arguments,
                outcome=outcome,
            )

    eliminated: list[str] = []
    if turn > 0 and turn % settings.tax_interval_turns == 0:
        eliminated = await _apply_survival_tax(session, turn)

    # Sweep every turn: $0 cash = eliminated, regardless of investments or goods.
    eliminated.extend(await _check_bankruptcies(session, turn))

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
