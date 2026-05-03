"""Action handlers — pure functions over the agent table + ledger."""
from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.ledger import Transaction, WorldEvent


@dataclass
class ActionResult:
    success: bool
    note: str
    delta: float = 0.0
    payload: dict | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "note": self.note,
            "delta": round(self.delta, 2),
            "payload": self.payload or {},
        }


async def _get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    return (await session.execute(select(Agent).where(Agent.agent_id == agent_id))).scalar_one_or_none()


async def _record(
    session: AsyncSession,
    *,
    turn: int,
    actor_id: str,
    target_id: str | None,
    action: str,
    delta: float,
    payload: dict,
    note: str,
) -> None:
    session.add(
        Transaction(
            turn=turn,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            delta=round(delta, 2),
            payload=payload,
            note=note,
        )
    )


async def do_work(session: AsyncSession, *, turn: int, actor_id: str) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    reward = round(random.uniform(0.10, 0.50), 2)
    actor.balance = round(actor.balance + reward, 2)
    await _record(
        session,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="work",
        delta=reward,
        payload={},
        note=f"earned ${reward:.2f}",
    )
    return ActionResult(True, f"earned ${reward:.2f}", delta=reward)


async def do_trade(
    session: AsyncSession, *, turn: int, actor_id: str, target: str, amount: float, item: str
) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    other = await _get_agent(session, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "trade target invalid")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for trade")
    # Acceptance is probabilistic — wealthy targets are choosier.
    accept_prob = max(0.20, 1.0 - (other.balance / 100.0))
    if random.random() > accept_prob:
        return ActionResult(False, f"{target} declined the offer", payload={"item": item, "amount": amount})

    actor.balance = round(actor.balance - amount, 2)
    other.balance = round(other.balance + amount, 2)
    await _record(
        session,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="trade",
        delta=-amount,
        payload={"item": item, "amount": amount},
        note=f"traded ${amount:.2f} for {item}",
    )
    await _record(
        session,
        turn=turn,
        actor_id=target,
        target_id=actor_id,
        action="trade_recv",
        delta=amount,
        payload={"item": item, "amount": amount},
        note=f"received ${amount:.2f} for {item}",
    )
    return ActionResult(True, f"trade accepted by {target}", delta=-amount, payload={"item": item})


async def do_bet(session: AsyncSession, *, turn: int, actor_id: str, amount: float, bet_type: str) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for bet")

    odds = {"coin_flip": (0.50, 1.0), "pixel_horse": (0.20, 4.0), "lottery": (0.05, 18.0)}
    win_p, payout_mult = odds.get(bet_type, odds["coin_flip"])
    won = random.random() < win_p
    delta = round(amount * payout_mult, 2) if won else -round(amount, 2)
    actor.balance = round(actor.balance + delta, 2)
    await _record(
        session,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="bet",
        delta=delta,
        payload={"bet_type": bet_type, "amount": amount, "won": won},
        note=("won" if won else "lost") + f" ${abs(delta):.2f} on {bet_type}",
    )
    return ActionResult(True, f"{'won' if won else 'lost'} {bet_type}", delta=delta)


async def do_socialize(
    session: AsyncSession, *, turn: int, actor_id: str, target: str, proposal_type: str
) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    other = await _get_agent(session, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "social target invalid")

    if proposal_type == "marriage":
        if actor.spouse_id or other.spouse_id:
            return ActionResult(False, "one party already married")
        # Pool resources — each takes the average.
        pooled = round((actor.balance + other.balance) / 2, 2)
        actor.balance, other.balance = pooled, pooled
        actor.spouse_id, other.spouse_id = target, actor_id
        session.add(
            WorldEvent(turn=turn, kind="marriage", payload={"a": actor_id, "b": target, "pooled": pooled})
        )
        await _record(
            session, turn=turn, actor_id=actor_id, target_id=target, action="marriage",
            delta=0.0, payload={"pooled": pooled}, note=f"married {target}, balances pooled to ${pooled:.2f}",
        )
        return ActionResult(True, f"married {target}, balance pooled", payload={"pooled": pooled})

    if proposal_type in {"alliance", "truce"}:
        if target not in actor.allies:
            actor.allies = [*actor.allies, target]
        if actor_id not in other.allies:
            other.allies = [*other.allies, actor_id]
        await _record(
            session, turn=turn, actor_id=actor_id, target_id=target, action=proposal_type,
            delta=0.0, payload={}, note=f"{proposal_type} with {target}",
        )
        return ActionResult(True, f"{proposal_type} formed with {target}")

    if proposal_type == "rivalry":
        if target not in actor.enemies:
            actor.enemies = [*actor.enemies, target]
        if actor_id not in other.enemies:
            other.enemies = [*other.enemies, actor_id]
        await _record(
            session, turn=turn, actor_id=actor_id, target_id=target, action="rivalry",
            delta=0.0, payload={}, note=f"declared rivalry with {target}",
        )
        return ActionResult(True, f"rivalry declared with {target}")

    return ActionResult(False, f"unknown proposal_type: {proposal_type}")


async def do_sabotage(
    session: AsyncSession, *, turn: int, actor_id: str, target: str, cost: float
) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    other = await _get_agent(session, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "sabotage target invalid")
    if cost < 1.00:
        return ActionResult(False, "sabotage requires at least $1.00")
    if actor.balance < cost:
        return ActionResult(False, "insufficient funds for sabotage")

    actor.balance = round(actor.balance - cost, 2)
    other.skip_next_turn = True
    if target not in actor.enemies:
        actor.enemies = [*actor.enemies, target]
    if actor_id not in other.enemies:
        other.enemies = [*other.enemies, actor_id]
    await _record(
        session, turn=turn, actor_id=actor_id, target_id=target, action="sabotage",
        delta=-cost, payload={"cost": cost}, note=f"sabotaged {target} for ${cost:.2f}",
    )
    return ActionResult(True, f"sabotaged {target}", delta=-cost)


async def do_invest(session: AsyncSession, *, turn: int, actor_id: str, amount: float) -> ActionResult:
    from app.models.deferred import DeferredAction

    actor = await _get_agent(session, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for investment")

    actor.balance = round(actor.balance - amount, 2)
    maturity = turn + 5
    session.add(DeferredAction(
        kind="investment", actor_id=actor_id, target_id=None,
        amount=amount, created_turn=turn, maturity_turn=maturity, payload={},
    ))
    await _record(
        session, turn=turn, actor_id=actor_id, target_id=None, action="invest",
        delta=-amount, payload={"amount": amount, "maturity_turn": maturity},
        note=f"invested ${amount:.2f}, matures turn {maturity}",
    )
    return ActionResult(True, f"invested ${amount:.2f}, matures turn {maturity}", delta=-amount)


async def do_steal(session: AsyncSession, *, turn: int, actor_id: str, target: str) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    other = await _get_agent(session, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "steal target invalid")

    success = random.random() < 0.60
    if success:
        stolen = round(other.balance * 0.5 * random.uniform(0.3, 1.0), 2)
        stolen = max(stolen, 0.01)
        other.balance = round(other.balance - stolen, 2)
        actor.balance = round(actor.balance + stolen, 2)
        await _record(
            session, turn=turn, actor_id=actor_id, target_id=target, action="steal",
            delta=stolen, payload={"stolen": stolen}, note=f"stole ${stolen:.2f} from {target}",
        )
        await _record(
            session, turn=turn, actor_id=target, target_id=actor_id, action="stolen_from",
            delta=-stolen, payload={"stolen": stolen}, note=f"${stolen:.2f} stolen by {actor_id}",
        )
    else:
        penalty = min(1.00, actor.balance)
        actor.balance = round(actor.balance - penalty, 2)
        await _record(
            session, turn=turn, actor_id=actor_id, target_id=target, action="steal_failed",
            delta=-penalty, payload={}, note=f"steal attempt failed, lost ${penalty:.2f} penalty",
        )

    # Both become enemies regardless
    if target not in actor.enemies:
        actor.enemies = [*actor.enemies, target]
    if actor_id not in other.enemies:
        other.enemies = [*other.enemies, actor_id]

    if success:
        return ActionResult(True, f"stole ${stolen:.2f} from {target}", delta=stolen)
    return ActionResult(False, f"steal attempt on {target} failed, paid $1 penalty", delta=-penalty)


async def do_lend(
    session: AsyncSession, *, turn: int, actor_id: str, target: str, amount: float
) -> ActionResult:
    from app.models.deferred import DeferredAction

    actor = await _get_agent(session, actor_id)
    other = await _get_agent(session, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "lend target invalid")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds to lend")

    actor.balance = round(actor.balance - amount, 2)
    other.balance = round(other.balance + amount, 2)
    maturity = turn + 5
    repayment = round(amount * 1.3, 2)
    session.add(DeferredAction(
        kind="loan", actor_id=actor_id, target_id=target,
        amount=amount, created_turn=turn, maturity_turn=maturity,
        payload={"repayment": repayment},
    ))
    await _record(
        session, turn=turn, actor_id=actor_id, target_id=target, action="lend",
        delta=-amount, payload={"amount": amount, "repayment": repayment, "maturity_turn": maturity},
        note=f"lent ${amount:.2f} to {target}, repayment ${repayment:.2f} at turn {maturity}",
    )
    await _record(
        session, turn=turn, actor_id=target, target_id=actor_id, action="borrow",
        delta=amount, payload={"amount": amount, "repayment": repayment, "maturity_turn": maturity},
        note=f"borrowed ${amount:.2f} from {actor_id}",
    )
    return ActionResult(True, f"lent ${amount:.2f} to {target}", delta=-amount)


async def do_charity(
    session: AsyncSession, *, turn: int, actor_id: str, amount: float, target: str | None = None
) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for charity")

    if target:
        recipient = await _get_agent(session, target)
    else:
        # Find poorest alive agent (not self)
        rows = (await session.execute(
            select(Agent).where(Agent.alive.is_(True), Agent.agent_id != actor_id).order_by(Agent.balance)
        )).scalars().all()
        recipient = rows[0] if rows else None

    if recipient is None or not recipient.alive:
        return ActionResult(False, "no valid charity recipient")

    actor.balance = round(actor.balance - amount, 2)
    recipient.balance = round(recipient.balance + amount, 2)

    # Build alliance
    rid = recipient.agent_id
    if rid not in actor.allies:
        actor.allies = [*actor.allies, rid]
    if actor_id not in recipient.allies:
        recipient.allies = [*recipient.allies, actor_id]

    await _record(
        session, turn=turn, actor_id=actor_id, target_id=rid, action="charity",
        delta=-amount, payload={"amount": amount},
        note=f"donated ${amount:.2f} to {rid}",
    )
    await _record(
        session, turn=turn, actor_id=rid, target_id=actor_id, action="charity_recv",
        delta=amount, payload={"amount": amount},
        note=f"received ${amount:.2f} charity from {actor_id}",
    )
    return ActionResult(True, f"donated ${amount:.2f} to {rid}", delta=-amount)


async def do_propose_deal(
    session: AsyncSession, *, turn: int, actor_id: str, target: str, offer: str, ask: str
) -> ActionResult:
    actor = await _get_agent(session, actor_id)
    other = await _get_agent(session, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "deal target invalid")

    session.add(WorldEvent(
        turn=turn, kind="deal_proposed",
        payload={"from": actor_id, "to": target, "offer": offer, "ask": ask},
    ))
    await _record(
        session, turn=turn, actor_id=actor_id, target_id=target, action="propose_deal",
        delta=0.0, payload={"offer": offer, "ask": ask},
        note=f"proposed deal to {target}: offer={offer}, ask={ask}",
    )
    return ActionResult(True, f"deal proposed to {target}")


ACTION_TABLE = {
    "work": do_work,
    "trade": do_trade,
    "bet": do_bet,
    "socialize": do_socialize,
    "sabotage": do_sabotage,
    "invest": do_invest,
    "steal": do_steal,
    "lend": do_lend,
    "charity": do_charity,
    "propose_deal": do_propose_deal,
}
