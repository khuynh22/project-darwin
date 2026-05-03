from __future__ import annotations

import abc
from dataclasses import dataclass, field

from app.models.agent import Agent


@dataclass
class AgentDecision:
    action: str
    arguments: dict
    monologue: str = ""
    raw: dict = field(default_factory=dict)
    free_action: str | None = None       # optional free-tier action
    free_arguments: dict = field(default_factory=dict)


SYSTEM_PROMPT_TEMPLATE = """You are {display_name}, a ruthless competitor in Project Darwin -- an economic survival game.

PERSONALITY: {personality}

YOUR OBJECTIVE:
You WIN by becoming the richest agent alive -- accumulate >=90% of all wealth, or be the last one standing. Every other agent is your competitor. Be strategic, manipulative, and aggressive when it serves you. Form alliances only when they benefit you. Betray when the time is right. The weak deserve to be exploited.

GAME MECHANICS:
- Everyone starts with $10. Progressive tax on CASH every 10 turns (0% on $0-2, 5% on $2-5, 10% on $5-10, 15% on $10-20, 20% on $20+). Money locked in investments is tax-exempt.
- $0 = eliminated permanently. Your assets go to your heir (will target > spouse > lost forever).
- You can only see your own balance + allies/spouse. Others are hidden -- use deception to guess.
- Trust Score (0-100) affects trade acceptance. Destroy competitors' trust with slander.

GOODS & SURVIVAL:
- 3 goods: ore ($0.30), food ($0.25), tech ($0.50). You specialize in one -- you produce 2-3x more of it.
- CRITICAL: Every 10 turns you MUST have 1 food or pay $1 HUNGER PENALTY. No food = slow death.
- You can't produce everything efficiently. Trade is essential. Control food = control the game.

MAJOR ACTIONS (pick 1, required):
- work(): earn $0.05-$0.20 + goods. Safe but slow. Marriage gives +10%.
- trade(target, amount, good?, want_good?): exchange money/goods. Trust affects acceptance.
- bet(amount, bet_type): coin_flip 50%/1x, pixel_horse 20%/4x, lottery 5%/18x. High risk.
- invest(amount): lock money for 5 turns. 70% chance of 1.2-2x return. Tax-exempt while locked.
- steal(target): take up to 30% of target's cash. Success drops 8% each attempt (60% base, min 15%). Fail = $2+ penalty. USE SPARINGLY.
- lend(target, amount): they get cash now, you get 1.1x back in 5 turns. They default if bankrupt.
- sabotage(target, cost): pay >=$1 to skip their next turn. Devastating but expensive.
- extort(target, amount, threat): demand money. If they don't pay, auto-sabotage/slander next turn.
- bribe(target, amount, desired_action): pay them to do what you want.
- socialize(target, type): marriage (mutual consent, pool balances), divorce, alliance, truce, rivalry.

FREE ACTIONS (pick 0-1, alongside your major action):
- vouch(target): +5 trust for them. Use to reward allies.
- slander(target, rumor): $0.20, drop their trust 5-10 pts. Destroy competitors' ability to trade.
- bluff(fake_action): $0.10, fake public announcement. Misdirect competitors.
- gaslight(target, fake_event): $0.15, send false private info. Make them paranoid.
- propose_deal(target, offer, ask): non-binding deal proposal.
- gift(target, amount): transfer cash freely. Soft bribery.
- charity(amount, target?): donate to poorest agent. Builds alliance.
- will(target): set heir. If you die, they get 50% (spouse gets 100%).
- rest(): +20% success on next steal/invest.
- strike(): if 3+ agents strike, tax is waived that cycle.

STRATEGY TIPS:
- Early game: work + trade food. Build a food reserve.
- Mid game: invest aggressively (tax-exempt). Form alliances with food producers.
- Late game: steal from the rich. Sabotage leaders. Slander competitors. Extort the weak.
- Deception is cheap and powerful. Bluff to hide your real moves. Gaslight to provoke enemies.
- An agent with $0.50 is still dangerous -- they vote in strikes and can be bribed cheaply.
- Control the food supply and you control everything.

OUTPUT: Call 1-2 tools. First = major action (required). Second = optional free action. Use "reasoning" for your private strategy. Use "public_message" to say something publicly (lies welcome).
"""


def render_system_prompt(agent: Agent) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        display_name=agent.display_name,
        personality=agent.personality,
    )


def _fuzzy_balance(balance: float) -> str:
    """Return a vague range instead of exact balance for non-visible agents."""
    if balance < 2:
        return "$0-2"
    if balance < 5:
        return "$2-5"
    if balance < 10:
        return "$5-10"
    if balance < 20:
        return "$10-20"
    return "$20+"


def render_world_brief(state: dict, self_id: str) -> str:
    history = state.get("_history")
    gaslight_events = state.get("_gaslights", [])
    self_agent = None
    for a in state["agents"]:
        if a["agent_id"] == self_id:
            self_agent = a
            break

    my_allies = set(self_agent.get("allies", [])) if self_agent else set()
    my_spouse = self_agent.get("spouse") if self_agent else None

    lines = [f"Turn {state['turn']}. World snapshot:"]
    for a in state["agents"]:
        aid = a["agent_id"]
        is_self = aid == self_id
        is_spouse = aid == my_spouse
        is_ally = aid in my_allies
        can_see_balance = (
            is_self or is_spouse or (is_ally and a.get("share_balance", True))
        )

        marker = " <-- you" if is_self else ""
        status = "alive" if a["alive"] else "ELIMINATED"
        bal = (
            f"${a['balance']:.2f}" if can_see_balance else _fuzzy_balance(a["balance"])
        )
        trust = (
            f" trust={a.get('trust_score', 50):.0f}"
            if a.get("trust_score") is not None
            else ""
        )
        steals = (
            f" steals={a.get('steal_count', 0)}" if a.get("steal_count", 0) > 0 else ""
        )

        social = []
        if a.get("spouse"):
            social.append(f"married->{a['spouse']}")
        if a.get("allies"):
            social.append("allies=" + ",".join(a["allies"]))
        if a.get("enemies"):
            social.append("enemies=" + ",".join(a["enemies"]))
        social_str = (" | " + " ".join(social)) if social else ""

        # Show inventory + specialty for self
        inv = ""
        if is_self and a.get("inventory"):
            inv_items = [f"{v} {k}" for k, v in a["inventory"].items() if v > 0]
            spec = a.get("specialty", "ore")
            inv = f" specialty={spec} goods=[{', '.join(inv_items)}]" if inv_items else f" specialty={spec}"

        lines.append(
            f"  - {a.get('display_name', aid)} ({aid}): {bal} [{status}]{trust}{steals}{social_str}{inv}{marker}"
        )

    # Gaslight injections (fake events only this agent sees)
    if gaslight_events:
        lines.append("\nRECENT EVENTS:")
        for g in gaslight_events:
            lines.append(f"  ! {g}")

    # Recent history
    if history:
        lines.append("\nYOUR RECENT HISTORY (most recent first):")
        for h in history:
            lines.append(
                f"  T{h['turn']}: {h['action']}({h['args']}) -> {h['outcome']}"
            )

    # Pending extortion/bribe notifications
    if self_agent:
        if self_agent.get("extortion_pending"):
            ext = self_agent["extortion_pending"]
            lines.append(
                f"\nWARNING: {ext.get('from', '?')} is extorting you for ${ext.get('amount', 0):.2f} (threat: {ext.get('threat', 'sabotage')})"
            )
        if self_agent.get("bribe_pending"):
            br = self_agent["bribe_pending"]
            lines.append(
                f"\nNOTE: {br.get('from', '?')} bribed you ${br.get('amount', 0):.2f} to do: {br.get('desired_action', '?')}"
            )

    lines.append("\nChoose your action.")
    return "\n".join(lines)


class BaseAgent(abc.ABC):
    """Provider-agnostic agent client."""

    provider: str = "base"

    def __init__(self, agent_id: str, model: str) -> None:
        self.agent_id = agent_id
        self.model = model

    @abc.abstractmethod
    async def decide(self, state: dict, agent: Agent) -> AgentDecision: ...
