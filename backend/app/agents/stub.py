"""Deterministic stub agent -- exercises the full pipeline without API calls."""

from __future__ import annotations

import random

from app.agents.base import AgentDecision, BaseAgent
from app.models.agent import Agent

# Default bias used for all stub agents (no hardcoded agent IDs).
DEFAULT_BIAS = {
    "work": 4,
    "trade": 2,
    "bet": 1,
    "socialize": 2,
    "sabotage": 1,
    "invest": 2,
    "steal": 1,
    "lend": 1,
    "charity": 1,
    "propose_deal": 1,
    "slander": 1,
    "vouch": 1,
    "gift": 1,
    "bluff": 1,
    "extort": 1,
    "strike": 0,
    "rest": 1,
    "will": 0,
    "gaslight": 1,
    "bribe": 1,
}

# Actions that require a target agent
_TARGET_ACTIONS = {
    "trade",
    "socialize",
    "sabotage",
    "steal",
    "lend",
    "charity",
    "propose_deal",
    "slander",
    "vouch",
    "gift",
    "extort",
    "gaslight",
    "bribe",
}

# Actions that require money
_COSTLY_ACTIONS = {
    "bet": 0.50,
    "sabotage": 1.00,
    "invest": 0.10,
    "lend": 0.10,
    "charity": 0.10,
    "slander": 0.20,
    "gift": 0.10,
    "bluff": 0.10,
    "extort": 0.0,
    "gaslight": 0.15,
    "bribe": 0.10,
    "trade": 0.0,
}


_FREE_SET = {
    "vouch",
    "will",
    "rest",
    "strike",
    "bluff",
    "propose_deal",
    "slander",
    "gaslight",
    "gift",
    "charity",
}


class StubAgent(BaseAgent):
    provider = "stub"

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        decision = self._pick_major(state, agent)
        # 40% chance to also pick a free action
        if random.random() < 0.4:
            others = [
                a
                for a in state["agents"]
                if a["agent_id"] != agent.agent_id and a["alive"]
            ]
            target = random.choice(others)["agent_id"] if others else None
            free = random.choice(["vouch", "bluff", "propose_deal", "slander"])
            if free == "vouch" and target:
                decision.free_action = "vouch"
                decision.free_arguments = {"target": target}
            elif free == "bluff":
                decision.free_action = "bluff"
                decision.free_arguments = {"fake_action": "invested $5.00"}
            elif free == "slander" and target and agent.balance >= 0.20:
                decision.free_action = "slander"
                decision.free_arguments = {"target": target, "rumor": "unreliable"}
            elif free == "propose_deal" and target:
                decision.free_action = "propose_deal"
                decision.free_arguments = {
                    "target": target,
                    "offer": "$0.50",
                    "ask": "alliance",
                }
        return decision

    def _pick_major(self, state: dict, agent: Agent) -> AgentDecision:
        bias = DEFAULT_BIAS
        choices: list[str] = []
        for action, weight in bias.items():
            choices.extend([action] * max(0, weight))
        action = random.choice(choices) if choices else "work"

        # Affordability check
        min_cost = _COSTLY_ACTIONS.get(action, 0)
        if min_cost > 0 and agent.balance < min_cost:
            action = "work"

        others = [
            a for a in state["agents"] if a["agent_id"] != agent.agent_id and a["alive"]
        ]
        if not others and action in _TARGET_ACTIONS:
            action = "work"

        if action == "work":
            return AgentDecision(
                "work", {}, monologue=f"({agent.display_name}) Steady work."
            )

        target = random.choice(others)["agent_id"] if others else ""

        if action == "trade":
            amount = round(min(0.30, agent.balance / 4), 2) or 0.05
            good = random.choice(["ore", "food", "tech", None])
            return AgentDecision(
                "trade",
                {"target": target, "amount": amount, "good": good},
                monologue=f"({agent.display_name}) Trading with {target}.",
            )

        if action == "bet":
            amount = round(min(1.00, max(0.10, agent.balance / 5)), 2)
            return AgentDecision(
                "bet",
                {
                    "amount": amount,
                    "bet_type": random.choice(["coin_flip", "pixel_horse", "lottery"]),
                },
                monologue=f"({agent.display_name}) Taking a gamble.",
            )

        if action == "socialize":
            proposals = ["alliance", "truce", "marriage", "rivalry"]
            if agent.spouse_id:
                proposals = ["alliance", "truce", "rivalry", "divorce"]
            proposal = random.choice(proposals)
            t = agent.spouse_id if proposal == "divorce" else target
            return AgentDecision(
                "socialize",
                {"target": t, "proposal_type": proposal},
                monologue=f"({agent.display_name}) {proposal} with {t}.",
            )

        if action == "sabotage":
            return AgentDecision(
                "sabotage",
                {"target": target, "cost": 1.00},
                monologue=f"({agent.display_name}) Sabotaging {target}.",
            )

        if action == "invest":
            amount = round(min(2.00, max(0.10, agent.balance / 5)), 2)
            return AgentDecision(
                "invest",
                {"amount": amount},
                monologue=f"({agent.display_name}) Investing.",
            )

        if action == "steal":
            return AgentDecision(
                "steal",
                {"target": target},
                monologue=f"({agent.display_name}) Stealing from {target}.",
            )

        if action == "lend":
            amount = round(min(1.00, max(0.10, agent.balance / 6)), 2)
            return AgentDecision(
                "lend",
                {"target": target, "amount": amount},
                monologue=f"({agent.display_name}) Lending to {target}.",
            )

        if action == "charity":
            amount = round(min(0.50, max(0.10, agent.balance / 8)), 2)
            return AgentDecision(
                "charity",
                {"amount": amount, "target": target},
                monologue=f"({agent.display_name}) Donating to {target}.",
            )

        if action == "propose_deal":
            return AgentDecision(
                "propose_deal",
                {"target": target, "offer": "$0.50", "ask": "alliance"},
                monologue=f"({agent.display_name}) Proposing deal to {target}.",
            )

        if action == "slander":
            return AgentDecision(
                "slander",
                {"target": target, "rumor": "untrustworthy"},
                monologue=f"({agent.display_name}) Slandering {target}.",
            )

        if action == "vouch":
            return AgentDecision(
                "vouch",
                {"target": target},
                monologue=f"({agent.display_name}) Vouching for {target}.",
            )

        if action == "gift":
            amount = round(min(0.30, max(0.10, agent.balance / 10)), 2)
            return AgentDecision(
                "gift",
                {"target": target, "amount": amount},
                monologue=f"({agent.display_name}) Gifting to {target}.",
            )

        if action == "bluff":
            return AgentDecision(
                "bluff",
                {"fake_action": "invested $3.00"},
                monologue=f"({agent.display_name}) Bluffing.",
            )

        if action == "extort":
            return AgentDecision(
                "extort",
                {"target": target, "amount": 1.00, "threat": "sabotage"},
                monologue=f"({agent.display_name}) Extorting {target}.",
            )

        if action == "strike":
            return AgentDecision(
                "strike", {}, monologue=f"({agent.display_name}) Striking."
            )

        if action == "rest":
            return AgentDecision(
                "rest", {}, monologue=f"({agent.display_name}) Resting."
            )

        if action == "will":
            return AgentDecision(
                "will",
                {"target": target},
                monologue=f"({agent.display_name}) Setting will to {target}.",
            )

        if action == "gaslight":
            return AgentDecision(
                "gaslight",
                {"target": target, "fake_event": "Someone slandered you"},
                monologue=f"({agent.display_name}) Gaslighting {target}.",
            )

        if action == "bribe":
            amount = round(min(0.50, max(0.10, agent.balance / 8)), 2)
            return AgentDecision(
                "bribe",
                {"target": target, "amount": amount, "desired_action": "work"},
                monologue=f"({agent.display_name}) Bribing {target}.",
            )

        return AgentDecision("work", {}, monologue="(fallback) work.")
