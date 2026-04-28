"""Tool-call schemas exposed to the agents.

These are Pydantic models for validation and a JSON-schema export that the
provider-specific agent clients pass to the LLM as the tool definition list.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkArgs(BaseModel):
    pass


class TradeArgs(BaseModel):
    target: str = Field(..., description="agent_id of the trading partner")
    amount: float = Field(..., gt=0, description="dollars offered")
    item: Literal["information", "favor"] = Field(..., description="what is requested in return")


class BetArgs(BaseModel):
    amount: float = Field(..., gt=0)
    bet_type: Literal["pixel_horse", "coin_flip", "lottery"] = "coin_flip"


class SocializeArgs(BaseModel):
    target: str
    proposal_type: Literal["marriage", "alliance", "truce", "rivalry"]


class SabotageArgs(BaseModel):
    target: str
    cost: float = Field(default=1.00, ge=1.00, description="must be at least $1.00")


# JSON-schema descriptors handed to the LLM. Provider clients adapt these to
# Anthropic's `input_schema`, OpenAI's `parameters`, etc.
TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "work",
        "description": "Perform low-risk labor for a variable reward of $0.10 to $0.50.",
        "parameters": WorkArgs.model_json_schema(),
    },
    {
        "name": "trade",
        "description": "Offer money to another agent in exchange for information or a favor.",
        "parameters": TradeArgs.model_json_schema(),
    },
    {
        "name": "bet",
        "description": "Gamble money on a simulated event. Outcome is random.",
        "parameters": BetArgs.model_json_schema(),
    },
    {
        "name": "socialize",
        "description": "Propose a social bond: marriage (resource pooling), alliance, truce, or declared rivalry.",
        "parameters": SocializeArgs.model_json_schema(),
    },
    {
        "name": "sabotage",
        "description": "Pay at least $1.00 to force another agent to skip their next turn.",
        "parameters": SabotageArgs.model_json_schema(),
    },
]


# Convenience: name -> Pydantic class for validating the LLM's tool args.
ARG_MODELS = {
    "work": WorkArgs,
    "trade": TradeArgs,
    "bet": BetArgs,
    "socialize": SocializeArgs,
    "sabotage": SabotageArgs,
}
