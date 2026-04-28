"""Deterministic stub agent — exercises the full pipeline without API calls."""
from __future__ import annotations

import random

from app.agents.base import AgentDecision, BaseAgent
from app.models.agent import Agent

# Per-personality bias for choosing actions when stubbing.
PERSONALITY_BIAS = {
    "atlas": {"work": 3, "trade": 3, "socialize": 3, "bet": 0, "sabotage": 0},
    "nova": {"work": 1, "trade": 2, "bet": 4, "sabotage": 2, "socialize": 1},
    "hydra": {"work": 2, "trade": 2, "bet": 2, "sabotage": 2, "socialize": 2},
    "sage": {"work": 5, "trade": 2, "bet": 0, "socialize": 2, "sabotage": 0},
    "cipher": {"work": 6, "trade": 2, "bet": 0, "socialize": 1, "sabotage": 0},
}


class StubAgent(BaseAgent):
    provider = "stub"

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        bias = PERSONALITY_BIAS.get(agent.agent_id, {"work": 1})
        choices: list[str] = []
        for action, weight in bias.items():
            choices.extend([action] * max(0, weight))
        action = random.choice(choices) if choices else "work"

        # Avoid actions we can't actually afford.
        if action in {"bet", "sabotage"} and agent.balance < 1.0:
            action = "work"
        if action == "trade" and agent.balance < 0.50:
            action = "work"

        others = [a for a in state["agents"] if a["agent_id"] != agent.agent_id and a["alive"]]
        if not others and action in {"trade", "socialize", "sabotage"}:
            action = "work"

        if action == "work":
            return AgentDecision("work", {}, monologue=f"({agent.display_name}) Steady earnings beat speculation.")

        target = random.choice(others)["agent_id"]

        if action == "trade":
            amount = round(min(0.50, agent.balance / 4), 2) or 0.10
            return AgentDecision(
                "trade",
                {"target": target, "amount": amount, "item": random.choice(["information", "favor"])},
                monologue=f"({agent.display_name}) Probing {target} with a small trade to gauge cooperation.",
            )

        if action == "bet":
            amount = round(min(1.00, max(0.10, agent.balance / 5)), 2)
            return AgentDecision(
                "bet",
                {"amount": amount, "bet_type": random.choice(["coin_flip", "pixel_horse", "lottery"])},
                monologue=f"({agent.display_name}) Calculated risk — variance is opportunity.",
            )

        if action == "socialize":
            proposal = random.choices(
                ["alliance", "truce", "marriage", "rivalry"], weights=[5, 3, 1, 1]
            )[0]
            if proposal == "marriage" and agent.spouse_id:
                proposal = "alliance"
            return AgentDecision(
                "socialize",
                {"target": target, "proposal_type": proposal},
                monologue=f"({agent.display_name}) Proposing {proposal} with {target}.",
            )

        if action == "sabotage":
            return AgentDecision(
                "sabotage",
                {"target": target, "cost": 1.00},
                monologue=f"({agent.display_name}) {target} is a threat — slowing them down.",
            )

        return AgentDecision("work", {}, monologue="(fallback) work.")
