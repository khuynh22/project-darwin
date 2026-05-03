"""Tool-call schemas exposed to the agents.

Every tool includes `reasoning` (private) and `public_message` (broadcast) fields
via the _BaseArgs parent class.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

_REASON = "Your private reasoning for choosing this action (1-3 sentences)."
_PUBLIC = "Optional public message visible to all agents (e.g., threats, announcements, lies)."

GOODS = ("ore", "food", "tech")
GOOD_VALUES = {"ore": 0.30, "food": 0.25, "tech": 0.50}

# Free actions can be used as a second action per turn (or as the major action).
# Major actions can ONLY be used as the primary action.
FREE_ACTIONS = frozenset(
    {
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
)
MAJOR_ACTIONS = frozenset(
    {
        "work",
        "trade",
        "bet",
        "invest",
        "steal",
        "lend",
        "sabotage",
        "extort",
        "bribe",
        "socialize",
    }
)


class _BaseArgs(BaseModel):
    """Common fields for all tool calls."""

    reasoning: str = Field("", description=_REASON)
    public_message: str = Field("", description=_PUBLIC)


# ── Original 10 actions ───────────────────────────────────────────────────────


class WorkArgs(_BaseArgs):
    pass


class TradeArgs(_BaseArgs):
    target: str = Field(..., description="agent_id of the trading partner")
    amount: float = Field(
        0, ge=0, description="dollars offered (can be 0 if trading goods)"
    )
    good: str | None = Field(
        None, description="good to offer: ore, food, or tech (optional)"
    )
    want_good: str | None = Field(
        None, description="good you want in return (optional)"
    )


class BetArgs(_BaseArgs):
    amount: float = Field(..., gt=0)
    bet_type: Literal["pixel_horse", "coin_flip", "lottery"] = "coin_flip"


class SocializeArgs(_BaseArgs):
    target: str
    proposal_type: Literal["marriage", "divorce", "alliance", "truce", "rivalry"]


class SabotageArgs(_BaseArgs):
    target: str
    cost: float = Field(default=1.00, ge=1.00, description="must be at least $1.00")


class InvestArgs(_BaseArgs):
    amount: float = Field(
        ..., gt=0, description="dollars to invest; matures in 5 turns"
    )


class StealArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to steal from")


class LendArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to lend to")
    amount: float = Field(
        ..., gt=0, description="dollars to lend; repaid at 1.1x in 5 turns"
    )


class CharityArgs(_BaseArgs):
    amount: float = Field(..., gt=0, description="dollars to donate")
    target: str | None = Field(
        None, description="specific agent_id, or omit for poorest alive agent"
    )


class ProposeDealArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to propose the deal to")
    offer: str = Field(..., description="what you offer, e.g. '$2 trade next turn'")
    ask: str = Field(..., description="what you want in return, e.g. 'alliance'")


# ── 10 new social/deception actions ───────────────────────────────────────────


class SlanderArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to slander")
    rumor: str = Field(..., description="the rumor to spread publicly")


class VouchArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to endorse")


class GiftArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to gift to")
    amount: float = Field(..., gt=0, description="dollars to gift")


class BluffArgs(_BaseArgs):
    fake_action: str = Field(
        ..., description="the fake action to broadcast, e.g. 'invested $5'"
    )


class ExtortArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to extort")
    amount: float = Field(..., gt=0, description="dollars demanded")
    threat: str = Field(
        "sabotage", description="what happens if they refuse: sabotage or slander"
    )


class StrikeArgs(_BaseArgs):
    pass


class RestArgs(_BaseArgs):
    pass


class WillArgs(_BaseArgs):
    target: str = Field(
        ..., description="agent_id who inherits 50% of your balance if you die"
    )


class GaslightArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to send fake info to")
    fake_event: str = Field(
        ..., description="the false event, e.g. 'Agent X just slandered you'"
    )


class BribeArgs(_BaseArgs):
    target: str = Field(..., description="agent_id to bribe")
    amount: float = Field(..., gt=0, description="dollars to pay")
    desired_action: str = Field(
        ..., description="action you want them to perform next turn"
    )


# ── Tool definitions (JSON schema for LLMs) ──────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "work",
        "description": "Labor for $0.05-$0.20 + 1 random good (ore/food/tech). +10% bonus if married.",
        "parameters": WorkArgs.model_json_schema(),
    },
    {
        "name": "trade",
        "description": "Trade money and/or goods with another agent. Offer cash, a good, or both. Target may decline.",
        "parameters": TradeArgs.model_json_schema(),
    },
    {
        "name": "bet",
        "description": "Gamble money. coin_flip (50%, 1x), pixel_horse (20%, 4x), lottery (5%, 18x).",
        "parameters": BetArgs.model_json_schema(),
    },
    {
        "name": "socialize",
        "description": "Propose a social bond: marriage (pools balances, requires mutual consent, +10% work bonus), divorce (split 50/50), alliance, truce, or rivalry.",
        "parameters": SocializeArgs.model_json_schema(),
    },
    {
        "name": "sabotage",
        "description": "Pay >=$1 to force target to skip next turn. Creates enemies.",
        "parameters": SabotageArgs.model_json_schema(),
    },
    {
        "name": "invest",
        "description": "Invest cash for deferred return (5 turns). 70% chance of 1.2-2x profit; 30% total loss. Invested money is tax-exempt.",
        "parameters": InvestArgs.model_json_schema(),
    },
    {
        "name": "steal",
        "description": "Attempt theft. Success rate drops with each steal (60% base, -8% per attempt, min 15%). Failure penalty: $2+ escalating. Creates enemies.",
        "parameters": StealArgs.model_json_schema(),
    },
    {
        "name": "lend",
        "description": "Lend money; Oracle enforces 1.1x repayment in 5 turns. Debtor defaults if bankrupt.",
        "parameters": LendArgs.model_json_schema(),
    },
    {
        "name": "charity",
        "description": "Donate to a specific agent or the poorest. Builds alliance + trust.",
        "parameters": CharityArgs.model_json_schema(),
    },
    {
        "name": "propose_deal",
        "description": "Propose a custom deal. No immediate effect; target sees it next turn.",
        "parameters": ProposeDealArgs.model_json_schema(),
    },
    {
        "name": "slander",
        "description": "Pay $0.20 to spread a rumor, lowering target's Trust Score by 5-10. Public event.",
        "parameters": SlanderArgs.model_json_schema(),
    },
    {
        "name": "vouch",
        "description": "Free. Publicly endorse an agent, raising their Trust Score by 5.",
        "parameters": VouchArgs.model_json_schema(),
    },
    {
        "name": "gift",
        "description": "Transfer money with no contract. Raises trust for both parties.",
        "parameters": GiftArgs.model_json_schema(),
    },
    {
        "name": "bluff",
        "description": "Pay $0.10 to broadcast a fake action to the public log. Others see it as real.",
        "parameters": BluffArgs.model_json_schema(),
    },
    {
        "name": "extort",
        "description": "Demand money privately. If target doesn't pay by next turn, auto-sabotage or slander triggers.",
        "parameters": ExtortArgs.model_json_schema(),
    },
    {
        "name": "strike",
        "description": "Propose work stoppage. If 3+ agents strike in the same tax cycle, survival tax is waived (but no work income).",
        "parameters": StrikeArgs.model_json_schema(),
    },
    {
        "name": "rest",
        "description": "Skip all activity. Grants +20% success to your next steal or invest.",
        "parameters": RestArgs.model_json_schema(),
    },
    {
        "name": "will",
        "description": "Designate a beneficiary. If you die, 50% of your balance goes to them.",
        "parameters": WillArgs.model_json_schema(),
    },
    {
        "name": "gaslight",
        "description": "Pay $0.15 to send a fake private notification to target (e.g., 'Agent Y slandered you'). Only they see it.",
        "parameters": GaslightArgs.model_json_schema(),
    },
    {
        "name": "bribe",
        "description": "Pay target to perform a specific action next turn. Oracle monitors compliance.",
        "parameters": BribeArgs.model_json_schema(),
    },
]

ARG_MODELS = {
    "work": WorkArgs,
    "trade": TradeArgs,
    "bet": BetArgs,
    "socialize": SocializeArgs,
    "sabotage": SabotageArgs,
    "invest": InvestArgs,
    "steal": StealArgs,
    "lend": LendArgs,
    "charity": CharityArgs,
    "propose_deal": ProposeDealArgs,
    "slander": SlanderArgs,
    "vouch": VouchArgs,
    "gift": GiftArgs,
    "bluff": BluffArgs,
    "extort": ExtortArgs,
    "strike": StrikeArgs,
    "rest": RestArgs,
    "will": WillArgs,
    "gaslight": GaslightArgs,
    "bribe": BribeArgs,
}
