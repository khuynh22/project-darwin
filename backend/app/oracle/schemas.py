"""Tool-call schemas exposed to the agents.

Every tool includes `reasoning` (private) and `public_message` (broadcast) fields
via the _BaseArgs parent class.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.oracle import world_data as _world
from app.oracle.scheduler import DEFAULT_WAKE_BEATS, WAKE_TRIGGERS

_REASON = "Your private reasoning for choosing this action (1-3 sentences)."
_PUBLIC = "Optional public message visible to all agents (e.g., threats, announcements, lies)."

GOODS = tuple(_world.GOODS)
GOOD_VALUES = {good: row.base_price for good, row in _world.GOODS.items()}

# Free actions can be taken as a second action alongside a major one, or as the
# major action; major actions can only be primary.
FREE_ACTIONS = _world.FREE_ACTIONS
MAJOR_ACTIONS = _world.MAJOR_ACTIONS


_WAKE_AFTER = (
    "How many beats to sleep before acting again (0.5-25). Short means you act "
    "often and pay attention often; long means you conserve effort but hunger "
    "and tax keep draining while you sleep."
)
_WAKE_IF = (
    "Events that should wake you sooner than wake_after. Choose from: "
    + ", ".join(sorted(WAKE_TRIGGERS))
    + "."
)


class _BaseArgs(BaseModel):
    """Common fields for all tool calls."""

    reasoning: str = Field("", description=_REASON)
    public_message: str = Field("", description=_PUBLIC)
    wake_after: float = Field(DEFAULT_WAKE_BEATS, description=_WAKE_AFTER)
    wake_if: list[str] = Field(default_factory=list, description=_WAKE_IF)


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

class SignContractArgs(_BaseArgs):
    target: str = Field(..., description="agent_id of the counterparty")
    good: str = Field(..., description="good you commit to deliver: ore, food, or tech")
    qty: int = Field(..., gt=0, description="units you commit to deliver")
    pay: float = Field(..., ge=0, description="dollars the counterparty pays on delivery")
    deadline_turn: int = Field(
        ..., description="turn by which you must deliver; must be in the future"
    )


class StandForOfficeArgs(_BaseArgs):
    office: str = Field(
        ..., description="office to take: bank, auditor, arbiter, or collector"
    )


class DeclareArgs(_BaseArgs):
    claim_type: str = Field(
        ..., description="office_holder or contract_status"
    )
    subject: str = Field(
        ..., description="office name (bank/auditor/arbiter/collector) or contract id"
    )
    asserted_value: str = Field(
        ...,
        description=(
            "what you publicly assert: an agent_id or 'nobody' for an office, "
            "or open/fulfilled/breached for a contract"
        ),
    )


class AuditArgs(_BaseArgs):
    target: str = Field(..., description="agent_id whose true balance to inspect")


class FulfilContractArgs(_BaseArgs):
    contract_id: str = Field(..., description="id of your open contract, e.g. k1")


ARG_MODELS = {
    "work": WorkArgs,
    "sign_contract": SignContractArgs,
    "stand_for_office": StandForOfficeArgs,
    "audit": AuditArgs,
    "declare": DeclareArgs,
    "fulfil_contract": FulfilContractArgs,
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

# Descriptions come from shared/actions.json -- the same sentence the prompt
# prints under the building the agent is standing at, so the tool schema and
# the venue block cannot describe the action differently.
TOOL_DEFINITIONS: list[dict] = [
    {
        "name": action_id,
        "description": row.summary,
        "parameters": ARG_MODELS[action_id].model_json_schema(),
    }
    for action_id, row in _world.ACTIONS.items()
]
