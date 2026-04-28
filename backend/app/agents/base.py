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
- You start with $10. The survival tax of $0.50 is deducted from every alive agent every 10 turns.
- Bankruptcy at $0 eliminates you permanently.
- Goal: survive 500 turns OR hold >=90% of all wealth.
- Each turn you must choose ONE tool call: work, trade, bet, socialize, or sabotage.

TOOL SUMMARY:
- work(): low-risk labor, +$0.10 to +$0.50.
- trade(target, amount, item): pay another agent for "information" or "favor". They may decline (richer agents are pickier).
- bet(amount, bet_type): coin_flip (50/50, 1x), pixel_horse (20%, 4x), lottery (5%, 18x).
- socialize(target, proposal_type): marriage (pools both balances), alliance, truce, or rivalry.
- sabotage(target, cost): pay >=$1 to make target skip their next turn (creates an enemy).

OUTPUT CONTRACT: Always emit a private monologue describing your reasoning, then call exactly one tool. Be strategic and stay in character.
"""


def render_system_prompt(agent: Agent) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        display_name=agent.display_name,
        personality=agent.personality,
    )


def render_world_brief(state: dict, self_id: str) -> str:
    lines = [f"Turn {state['turn']}. World snapshot:"]
    for a in state["agents"]:
        marker = " <-- you" if a["agent_id"] == self_id else ""
        status = "alive" if a["alive"] else "ELIMINATED"
        social = []
        if a["spouse"]:
            social.append(f"married→{a['spouse']}")
        if a["allies"]:
            social.append("allies=" + ",".join(a["allies"]))
        if a["enemies"]:
            social.append("enemies=" + ",".join(a["enemies"]))
        social_str = (" | " + " ".join(social)) if social else ""
        lines.append(
            f"  - {a['display_name']} ({a['agent_id']}): ${a['balance']:.2f} [{status}]{social_str}{marker}"
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
    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        ...
