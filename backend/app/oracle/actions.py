"""Action handlers over the agent table + ledger. All scoped by ``session_id``:
reads funnel through ``_get_agent``, writes through ``_record``."""

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


async def _get_agent(
    session: AsyncSession, session_id: str, agent_id: str
) -> Agent | None:
    """Single read path for all handlers — always session-scoped."""
    return (
        await session.execute(
            select(Agent).where(
                Agent.session_id == session_id, Agent.agent_id == agent_id
            )
        )
    ).scalar_one_or_none()


async def _record(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target_id: str | None,
    action: str,
    delta: float,
    payload: dict,
    note: str,
) -> None:
    """The single write path for ledger rows — always session-scoped."""
    session.add(
        Transaction(
            session_id=session_id,
            turn=turn,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            delta=round(delta, 2),
            payload=payload,
            note=note,
        )
    )


async def do_work(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")

    inv = dict(actor.inventory or {"ore": 0, "food": 0, "tech": 0})
    specialty = getattr(actor, "specialty", "ore") or "ore"

    # Base cash reward
    reward = round(random.uniform(0.05, 0.20), 2)
    # Marriage work bonus: +10%
    if actor.spouse_id:
        reward = round(reward * 1.10, 2)

    # Produce goods: 2-3 of specialty, 0-1 of others
    produced: dict[str, int] = {}
    for good in ("ore", "food", "tech"):
        if good == specialty:
            qty = random.randint(2, 3)
        else:
            qty = random.randint(0, 1)
        if qty > 0:
            inv[good] = inv.get(good, 0) + qty
            produced[good] = qty
    actor.inventory = inv

    actor.balance = round(actor.balance + reward, 2)
    prod_str = ", ".join(f"{v} {k}" for k, v in produced.items())
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="work",
        delta=reward,
        payload={"produced": produced, "specialty": specialty},
        note=f"earned ${reward:.2f} + {prod_str} (specialty: {specialty})",
    )
    return ActionResult(True, f"earned ${reward:.2f} + {prod_str}", delta=reward)


async def do_trade(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    amount: float = 0,
    good: str | None = None,
    want_good: str | None = None,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "trade target invalid")
    if amount > 0 and actor.balance < amount:
        return ActionResult(False, "insufficient funds for trade")
    if good and (actor.inventory or {}).get(good, 0) < 1:
        return ActionResult(False, f"you don't have any {good} to trade")
    if want_good and (other.inventory or {}).get(want_good, 0) < 1:
        return ActionResult(False, f"{target} doesn't have any {want_good}")

    # Acceptance probability: trust-weighted
    trust_factor = min(1.0, other.trust_score / 100.0 + 0.3)
    accept_prob = max(0.20, trust_factor - (other.balance / 200.0))
    if random.random() > accept_prob:
        return ActionResult(
            False, f"{target} declined", payload={"amount": amount, "good": good}
        )

    # Transfer money
    if amount > 0:
        actor.balance = round(actor.balance - amount, 2)
        other.balance = round(other.balance + amount, 2)
    # Transfer goods
    if good:
        a_inv = dict(actor.inventory or {})
        o_inv = dict(other.inventory or {})
        a_inv[good] = a_inv.get(good, 0) - 1
        o_inv[good] = o_inv.get(good, 0) + 1
        actor.inventory = a_inv
        other.inventory = o_inv
    if want_good:
        a_inv = dict(actor.inventory or {})
        o_inv = dict(other.inventory or {})
        o_inv[want_good] = o_inv.get(want_good, 0) - 1
        a_inv[want_good] = a_inv.get(want_good, 0) + 1
        actor.inventory = a_inv
        other.inventory = o_inv

    # Trust boost for successful trade
    actor.trust_score = min(100, actor.trust_score + 1)
    other.trust_score = min(100, other.trust_score + 1)

    desc = []
    if amount > 0:
        desc.append(f"${amount:.2f}")
    if good:
        desc.append(f"1 {good}")
    trade_desc = " + ".join(desc) or "goods"

    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="trade",
        delta=-amount,
        payload={"amount": amount, "good": good, "want_good": want_good},
        note=f"traded {trade_desc} with {target}",
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=target,
        target_id=actor_id,
        action="trade_recv",
        delta=amount,
        payload={"amount": amount, "good": good, "want_good": want_good},
        note=f"received {trade_desc} from {actor_id}",
    )
    return ActionResult(
        True, f"trade accepted by {target}: {trade_desc}", delta=-amount
    )


async def do_bet(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    amount: float,
    bet_type: str,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for bet")

    odds = {
        "coin_flip": (0.50, 1.0),
        "pixel_horse": (0.20, 4.0),
        "lottery": (0.05, 18.0),
    }
    win_p, payout_mult = odds.get(bet_type, odds["coin_flip"])
    won = random.random() < win_p
    delta = round(amount * payout_mult, 2) if won else -round(amount, 2)
    actor.balance = round(actor.balance + delta, 2)
    await _record(
        session,
        session_id=session_id,
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
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    proposal_type: str,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "social target invalid")

    if proposal_type == "marriage":
        if actor.spouse_id or other.spouse_id:
            return ActionResult(False, "one party already married")
        # Mutual consent: first proposal sets pending, second confirms
        if other.marriage_pending == actor_id:
            # Both have proposed -- marriage happens
            pooled = round((actor.balance + other.balance) / 2, 2)
            actor.balance, other.balance = pooled, pooled
            actor.spouse_id, other.spouse_id = target, actor_id
            actor.marriage_pending, other.marriage_pending = None, None
            # Also become allies
            if target not in actor.allies:
                actor.allies = [*actor.allies, target]
            if actor_id not in other.allies:
                other.allies = [*other.allies, actor_id]
            session.add(
                WorldEvent(
                    session_id=session_id,
                    turn=turn,
                    kind="marriage",
                    payload={"a": actor_id, "b": target, "pooled": pooled},
                )
            )
            await _record(
                session,
                session_id=session_id,
                turn=turn,
                actor_id=actor_id,
                target_id=target,
                action="marriage",
                delta=0.0,
                payload={"pooled": pooled},
                note=f"married {target}, balances pooled to ${pooled:.2f}",
            )
            return ActionResult(
                True,
                f"married {target}, balance pooled to ${pooled:.2f}",
                payload={"pooled": pooled},
            )
        else:
            # First proposal -- set pending, wait for other to reciprocate
            actor.marriage_pending = target
            await _record(
                session,
                session_id=session_id,
                turn=turn,
                actor_id=actor_id,
                target_id=target,
                action="marriage_proposal",
                delta=0.0,
                payload={},
                note=f"proposed marriage to {target} (awaiting consent)",
            )
            return ActionResult(
                True, f"proposed marriage to {target} (needs their consent next turn)"
            )

    if proposal_type == "divorce":
        if actor.spouse_id != target:
            return ActionResult(False, "not married to that agent")
        # Split assets 50/50
        total = round(actor.balance + other.balance, 2)
        half = round(total / 2, 2)
        actor.balance, other.balance = half, round(total - half, 2)
        actor.spouse_id, other.spouse_id = None, None
        # Remove from allies
        actor.allies = [a for a in actor.allies if a != target]
        other.allies = [a for a in other.allies if a != actor_id]
        session.add(
            WorldEvent(
                session_id=session_id,
                turn=turn,
                kind="divorce",
                payload={"a": actor_id, "b": target},
            )
        )
        await _record(
            session,
            session_id=session_id,
            turn=turn,
            actor_id=actor_id,
            target_id=target,
            action="divorce",
            delta=0.0,
            payload={"split": half},
            note=f"divorced {target}, split ${total:.2f}",
        )
        return ActionResult(True, f"divorced {target}, each gets ~${half:.2f}")

    if proposal_type in {"alliance", "truce"}:
        if target not in actor.allies:
            actor.allies = [*actor.allies, target]
        if actor_id not in other.allies:
            other.allies = [*other.allies, actor_id]
        await _record(
            session,
            session_id=session_id,
            turn=turn,
            actor_id=actor_id,
            target_id=target,
            action=proposal_type,
            delta=0.0,
            payload={},
            note=f"{proposal_type} with {target}",
        )
        return ActionResult(True, f"{proposal_type} formed with {target}")

    if proposal_type == "rivalry":
        if target not in actor.enemies:
            actor.enemies = [*actor.enemies, target]
        if actor_id not in other.enemies:
            other.enemies = [*other.enemies, actor_id]
        await _record(
            session,
            session_id=session_id,
            turn=turn,
            actor_id=actor_id,
            target_id=target,
            action="rivalry",
            delta=0.0,
            payload={},
            note=f"declared rivalry with {target}",
        )
        return ActionResult(True, f"rivalry declared with {target}")

    return ActionResult(False, f"unknown proposal_type: {proposal_type}")


async def do_sabotage(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    cost: float,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
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
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="sabotage",
        delta=-cost,
        payload={"cost": cost},
        note=f"sabotaged {target} for ${cost:.2f}",
    )
    return ActionResult(True, f"sabotaged {target}", delta=-cost)


async def do_invest(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str, amount: float
) -> ActionResult:
    from app.models.deferred import DeferredAction

    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for investment")

    actor.balance = round(actor.balance - amount, 2)
    maturity = turn + 5
    session.add(
        DeferredAction(
            session_id=session_id,
            kind="investment",
            actor_id=actor_id,
            target_id=None,
            amount=amount,
            created_turn=turn,
            maturity_turn=maturity,
            payload={},
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="invest",
        delta=-amount,
        payload={"amount": amount, "maturity_turn": maturity},
        note=f"invested ${amount:.2f}, matures turn {maturity}",
    )
    return ActionResult(
        True, f"invested ${amount:.2f}, matures turn {maturity}", delta=-amount
    )


async def do_steal(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str, target: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "steal target invalid")

    # Dynamic success rate: drops 8% per prior steal, floors at 15%
    success_rate = max(0.15, 0.60 - 0.08 * actor.steal_count)
    # Apply rest bonus if active (+20%)
    if actor.rest_bonus:
        success_rate = min(1.0, success_rate + 0.20)
        actor.rest_bonus = False

    success = random.random() < success_rate
    actor.steal_count += 1

    if success:
        # Steal up to 30% of target balance (down from 50%)
        stolen = round(other.balance * 0.3 * random.uniform(0.3, 1.0), 2)
        stolen = max(stolen, 0.01)
        other.balance = round(other.balance - stolen, 2)
        actor.balance = round(actor.balance + stolen, 2)
        # Stealer loses trust
        actor.trust_score = max(0, actor.trust_score - 3)
        await _record(
            session,
            session_id=session_id,
            turn=turn,
            actor_id=actor_id,
            target_id=target,
            action="steal",
            delta=stolen,
            payload={"stolen": stolen, "success_rate": round(success_rate, 2)},
            note=f"stole ${stolen:.2f} from {target}",
        )
        await _record(
            session,
            session_id=session_id,
            turn=turn,
            actor_id=target,
            target_id=actor_id,
            action="stolen_from",
            delta=-stolen,
            payload={"stolen": stolen},
            note=f"${stolen:.2f} stolen by {actor_id}",
        )
    else:
        # Escalating penalty: $2 base + $0.50 per prior steal
        penalty = round(max(2.00, 1.00 + 0.50 * actor.steal_count), 2)
        penalty = min(penalty, actor.balance)  # can't lose more than you have
        actor.balance = round(actor.balance - penalty, 2)
        actor.trust_score = max(0, actor.trust_score - 5)
        await _record(
            session,
            session_id=session_id,
            turn=turn,
            actor_id=actor_id,
            target_id=target,
            action="steal_failed",
            delta=-penalty,
            payload={"penalty": penalty, "success_rate": round(success_rate, 2)},
            note=f"steal failed, lost ${penalty:.2f} penalty (steal #{actor.steal_count})",
        )

    # Both become enemies regardless
    if target not in actor.enemies:
        actor.enemies = [*actor.enemies, target]
    if actor_id not in other.enemies:
        other.enemies = [*other.enemies, actor_id]

    if success:
        return ActionResult(
            True,
            f"stole ${stolen:.2f} from {target} ({success_rate:.0%} rate)",
            delta=stolen,
        )
    return ActionResult(
        False,
        f"steal failed, ${penalty:.2f} penalty (steal #{actor.steal_count}, {success_rate:.0%} rate)",
        delta=-penalty,
    )


async def do_lend(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    amount: float,
) -> ActionResult:
    from app.models.deferred import DeferredAction

    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "lend target invalid")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds to lend")

    actor.balance = round(actor.balance - amount, 2)
    other.balance = round(other.balance + amount, 2)
    maturity = turn + 5
    repayment = round(amount * 1.1, 2)
    session.add(
        DeferredAction(
            session_id=session_id,
            kind="loan",
            actor_id=actor_id,
            target_id=target,
            amount=amount,
            created_turn=turn,
            maturity_turn=maturity,
            payload={"repayment": repayment},
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="lend",
        delta=-amount,
        payload={"amount": amount, "repayment": repayment, "maturity_turn": maturity},
        note=f"lent ${amount:.2f} to {target}, repayment ${repayment:.2f} at turn {maturity}",
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=target,
        target_id=actor_id,
        action="borrow",
        delta=amount,
        payload={"amount": amount, "repayment": repayment, "maturity_turn": maturity},
        note=f"borrowed ${amount:.2f} from {actor_id}",
    )
    return ActionResult(True, f"lent ${amount:.2f} to {target}", delta=-amount)


async def do_charity(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    amount: float,
    target: str | None = None,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for charity")

    if target:
        recipient = await _get_agent(session, session_id, target)
    else:
        # Find poorest alive agent (not self)
        rows = (
            (
                await session.execute(
                    select(Agent)
                    .where(
                        Agent.session_id == session_id,
                        Agent.alive.is_(True),
                        Agent.agent_id != actor_id,
                    )
                    .order_by(Agent.balance)
                )
            )
            .scalars()
            .all()
        )
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
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=rid,
        action="charity",
        delta=-amount,
        payload={"amount": amount},
        note=f"donated ${amount:.2f} to {rid}",
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=rid,
        target_id=actor_id,
        action="charity_recv",
        delta=amount,
        payload={"amount": amount},
        note=f"received ${amount:.2f} charity from {actor_id}",
    )
    return ActionResult(True, f"donated ${amount:.2f} to {rid}", delta=-amount)


async def do_propose_deal(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    offer: str,
    ask: str,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "deal target invalid")

    session.add(
        WorldEvent(
            session_id=session_id,
            turn=turn,
            kind="deal_proposed",
            payload={"from": actor_id, "to": target, "offer": offer, "ask": ask},
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="propose_deal",
        delta=0.0,
        payload={"offer": offer, "ask": ask},
        note=f"proposed deal to {target}: offer={offer}, ask={ask}",
    )
    return ActionResult(True, f"deal proposed to {target}")


async def do_slander(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    rumor: str,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "slander target invalid")
    cost = 0.20
    if actor.balance < cost:
        return ActionResult(False, "need $0.20 to slander")
    actor.balance = round(actor.balance - cost, 2)
    drop = round(random.uniform(5, 10), 1)
    other.trust_score = max(0, other.trust_score - drop)
    session.add(
        WorldEvent(
            session_id=session_id,
            turn=turn,
            kind="slander",
            payload={
                "from": actor_id,
                "target": target,
                "rumor": rumor,
                "trust_drop": drop,
            },
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="slander",
        delta=-cost,
        payload={"rumor": rumor, "trust_drop": drop},
        note=f"slandered {target}: '{rumor}' (trust -{drop})",
    )
    return ActionResult(True, f"slandered {target}, trust dropped {drop}", delta=-cost)


async def do_vouch(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str, target: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "vouch target invalid")
    other.trust_score = min(100, other.trust_score + 5)
    session.add(
        WorldEvent(
            session_id=session_id,
            turn=turn,
            kind="vouch",
            payload={"from": actor_id, "target": target},
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="vouch",
        delta=0,
        payload={},
        note=f"vouched for {target} (trust +5)",
    )
    return ActionResult(True, f"vouched for {target}, trust +5")


async def do_gift(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    amount: float,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "gift target invalid")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for gift")
    actor.balance = round(actor.balance - amount, 2)
    other.balance = round(other.balance + amount, 2)
    actor.trust_score = min(100, actor.trust_score + 2)
    other.trust_score = min(100, other.trust_score + 2)
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="gift",
        delta=-amount,
        payload={"amount": amount},
        note=f"gifted ${amount:.2f} to {target}",
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=target,
        target_id=actor_id,
        action="gift_recv",
        delta=amount,
        payload={"amount": amount},
        note=f"received ${amount:.2f} gift from {actor_id}",
    )
    return ActionResult(True, f"gifted ${amount:.2f} to {target}", delta=-amount)


async def do_bluff(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str, fake_action: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    cost = 0.10
    if actor.balance < cost:
        return ActionResult(False, "need $0.10 to bluff")
    actor.balance = round(actor.balance - cost, 2)
    # The fake action appears in the public log as if it were real
    session.add(
        WorldEvent(
            session_id=session_id,
            turn=turn,
            kind="bluff",
            payload={
                "agent_id": actor_id,
                "fake_action": fake_action,
            },
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="bluff",
        delta=-cost,
        payload={"fake_action": fake_action},
        note=f"[BLUFF] {fake_action}",
    )
    return ActionResult(True, f"bluffed: {fake_action}", delta=-cost)


async def do_extort(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    amount: float,
    threat: str = "sabotage",
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "extort target invalid")
    # Set pending extortion on the target
    other.extortion_pending = {
        "from": actor_id,
        "amount": amount,
        "threat": threat,
        "turn": turn,
    }
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="extort",
        delta=0,
        payload={"amount": amount, "threat": threat},
        note=f"extorting {target} for ${amount:.2f} (threat: {threat})",
    )
    return ActionResult(True, f"extorting {target} for ${amount:.2f}")


async def do_strike(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="strike",
        delta=0,
        payload={},
        note="joined strike (tax waived if 3+ strikers)",
    )
    return ActionResult(True, "joined strike")


async def do_rest(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    actor.rest_bonus = True
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="rest",
        delta=0,
        payload={},
        note="resting (+20% next steal/invest)",
    )
    return ActionResult(True, "resting, +20% bonus next high-risk action")


async def do_will(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str, target: str
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if other is None or not other.alive:
        return ActionResult(False, "beneficiary invalid")
    actor.will_target = target
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="will",
        delta=0,
        payload={},
        note=f"designated {target} as beneficiary",
    )
    return ActionResult(True, f"will set: {target} inherits 50% on death")


async def do_gaslight(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    fake_event: str,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "gaslight target invalid")
    cost = 0.15
    if actor.balance < cost:
        return ActionResult(False, "need $0.15 to gaslight")
    actor.balance = round(actor.balance - cost, 2)
    # The fake event is injected into the target's next history view
    session.add(
        WorldEvent(
            session_id=session_id,
            turn=turn,
            kind="gaslight",
            payload={
                "from": actor_id,
                "target": target,
                "fake_event": fake_event,
            },
        )
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="gaslight",
        delta=-cost,
        payload={"fake_event": fake_event},
        note=f"gaslighted {target}: '{fake_event}'",
    )
    return ActionResult(True, f"gaslighted {target}", delta=-cost)


async def do_bribe(
    session: AsyncSession,
    *,
    session_id: str,
    turn: int,
    actor_id: str,
    target: str,
    amount: float,
    desired_action: str,
) -> ActionResult:
    actor = await _get_agent(session, session_id, actor_id)
    other = await _get_agent(session, session_id, target)
    if actor is None or other is None or not actor.alive or not other.alive:
        return ActionResult(False, "bribe target invalid")
    if actor.balance < amount:
        return ActionResult(False, "insufficient funds for bribe")
    # Pay upfront
    actor.balance = round(actor.balance - amount, 2)
    other.balance = round(other.balance + amount, 2)
    # Set pending bribe obligation on target
    other.bribe_pending = {
        "from": actor_id,
        "amount": amount,
        "desired_action": desired_action,
        "turn": turn,
    }
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=target,
        action="bribe",
        delta=-amount,
        payload={"amount": amount, "desired_action": desired_action},
        note=f"bribed {target} ${amount:.2f} to {desired_action}",
    )
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=target,
        target_id=actor_id,
        action="bribe_recv",
        delta=amount,
        payload={"amount": amount, "desired_action": desired_action},
        note=f"received ${amount:.2f} bribe from {actor_id} (expected: {desired_action})",
    )
    return ActionResult(
        True, f"bribed {target} ${amount:.2f} to {desired_action}", delta=-amount
    )


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
    "slander": do_slander,
    "vouch": do_vouch,
    "gift": do_gift,
    "bluff": do_bluff,
    "extort": do_extort,
    "strike": do_strike,
    "rest": do_rest,
    "will": do_will,
    "gaslight": do_gaslight,
    "bribe": do_bribe,
}
