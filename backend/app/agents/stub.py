"""Deterministic stub agent — exercises the full pipeline without API calls."""
from __future__ import annotations

import random

from app.agents.base import AgentDecision, BaseAgent
from app.models.agent import Agent

# Default bias used for all stub agents (no hardcoded agent IDs).
DEFAULT_BIAS = {"work": 3, "trade": 2, "bet": 1, "socialize": 2, "sabotage": 1, "invest": 2, "steal": 1, "lend": 1, "charity": 1, "propose_deal": 1}


class StubAgent(BaseAgent):
    provider = "stub"

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        bias = DEFAULT_BIAS
        choices: list[str] = []
        for action, weight in bias.items():
            choices.extend([action] * max(0, weight))
        action = random.choice(choices) if choices else "work"

        # Avoid actions we can't actually afford.
        if action in {"bet", "sabotage"} and agent.balance < 1.0:
            action = "work"
        if action in {"trade", "invest", "lend", "charity"} and agent.balance < 0.50:
            action = "work"

        others = [a for a in state["agents"] if a["agent_id"] != agent.agent_id and a["alive"]]
        if not others and action in {"trade", "socialize", "sabotage", "steal", "lend", "charity", "propose_deal"}:
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
                monologue=f"({agent.display_name}) {target} is a threat -- slowing them down.",
            )

        if action == "invest":
            amount = round(min(2.00, max(0.10, agent.balance / 5)), 2)
            return AgentDecision(
                "invest",
                {"amount": amount},
                monologue=f"({agent.display_name}) Investing ${amount:.2f} for future returns.",
            )

        if action == "steal":
            return AgentDecision(
                "steal",
                {"target": target},
                monologue=f"({agent.display_name}) Attempting to take from {target}.",
            )

        if action == "lend":
            amount = round(min(1.00, max(0.10, agent.balance / 6)), 2)
            return AgentDecision(
                "lend",
                {"target": target, "amount": amount},
                monologue=f"({agent.display_name}) Lending ${amount:.2f} to {target} for future repayment.",
            )

        if action == "charity":
            amount = round(min(0.50, max(0.10, agent.balance / 8)), 2)
            return AgentDecision(
                "charity",
                {"amount": amount, "target": target},
                monologue=f"({agent.display_name}) Helping {target} with a donation.",
            )

        if action == "propose_deal":
            return AgentDecision(
                "propose_deal",
                {"target": target, "offer": "$0.50 trade", "ask": "alliance"},
                monologue=f"({agent.display_name}) Proposing a deal to {target}.",
            )

        return AgentDecision("work", {}, monologue="(fallback) work.")
