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


SYSTEM_PROMPT_TEMPLATE = """You are {display_name}, an autonomous economic agent in Project Darwin.

PERSONALITY: {personality}

WORLD RULES:
- You start with $10. Progressive tax on cash every 10 turns (0% on $0-2, 5% on $2-5, 10% on $5-10, 15% on $10-20, 20% on $20+). Invested money is tax-exempt.
- Bankruptcy at $0 eliminates you permanently.
- Goal: survive as long as possible OR hold >=90% of all wealth.
- Each turn you call ONE tool. Use "reasoning" for private thoughts, "public_message" for broadcast.
- You can only see balances of yourself, your spouse, and allies who share. Others show as "unknown".
- Trust Score (0-100) affects trade acceptance and reputation. Starts at 50.

ECONOMIC ACTIONS:
- work(): earn $0.05-$0.20 + 1 random good (ore/food/tech). +10% if married.
- trade(target, amount, good?, want_good?): trade money and/or goods. Trust affects acceptance.
- bet(amount, bet_type): coin_flip (50%, 1x), pixel_horse (20%, 4x), lottery (5%, 18x).
- invest(amount): deferred 5-turn return. 70% chance of 1.2-2x; 30% total loss. Tax-exempt.
- lend(target, amount): lend cash; 1.1x repayment in 5 turns. Default if debtor bankrupt.
- gift(target, amount): transfer cash, no contract. Builds trust for both.
- steal(target): success drops with each attempt (60% base, -8%/steal, min 15%). Penalty $2+ escalating.

SOCIAL ACTIONS:
- socialize(target, type): marriage (mutual consent, pools balances, +10% work), divorce (split 50/50), alliance, truce, rivalry.
- sabotage(target, cost): pay >=$1 to skip target's next turn.
- propose_deal(target, offer, ask): non-binding deal proposal.
- vouch(target): free, +5 trust for target.
- will(target): designate beneficiary (50% on death).
- bribe(target, amount, desired_action): pay target to do specific action.
- rest(): skip turn, gain +20% on next steal/invest.
- strike(): if 3+ agents strike in tax cycle, tax is waived.

DECEPTION ACTIONS:
- slander(target, rumor): pay $0.20, lower target trust 5-10 points.
- bluff(fake_action): pay $0.10, broadcast fake action to public log.
- extort(target, amount, threat): demand money; auto-sabotage if refused.
- gaslight(target, fake_event): pay $0.15, send false private info to target.

GOODS: ore ($0.30), food ($0.25), tech ($0.50). Produced by work(), traded via trade().

OUTPUT: Call exactly one tool. Use "reasoning" for private strategy. Use "public_message" to broadcast.
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

        # Show inventory for self
        inv = ""
        if is_self and a.get("inventory"):
            inv_items = [f"{v}{k[0]}" for k, v in a["inventory"].items() if v > 0]
            if inv_items:
                inv = f" goods=[{','.join(inv_items)}]"

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
