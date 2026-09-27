from __future__ import annotations

import json
import logging

from app.agents.base import (
    AgentDecision,
    BaseAgent,
    render_system_prompt,
    render_world_brief,
)
from app.models.agent import Agent
from app.oracle.scheduler import DEFAULT_WAKE_BEATS, WAKE_TRIGGERS
from app.oracle.schemas import TOOL_DEFINITIONS
from app.oracle.space import DEFAULT_VENUE
from app.oracle.world_data import actions_at

log = logging.getLogger(__name__)


def _tools_for_openai(venue: str | None = None, *, gated: bool = False) -> list[dict]:
    available = set(actions_at(venue or DEFAULT_VENUE, gated=gated))
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_DEFINITIONS
        if t["name"] in available
    ]


def _venue_fallback(wanted: str | None, *, venue: str) -> tuple[str, dict]:
    """What to do when a gated model offers nothing usable.

    Falling back to ``work`` is what the ungated client does, and under gating it
    is illegal everywhere but the Work Site -- an agent in the Bank would be
    rejected every wake forever. Walking toward whatever it asked for is both
    legal and a reasonable reading of the intent; with no intent to read, walk
    to the nearest other building rather than stand still.
    """
    from app.oracle.space import travel_ticks
    from app.oracle.world_data import ACTIONS, BUILT_VENUES, UBIQUITOUS_ACTIONS

    row = ACTIONS.get(wanted or "")
    if row is not None and row.id not in UBIQUITOUS_ACTIONS and row.venue != venue:
        return "travel", {"venue": row.venue}
    others = [vid for vid, v in BUILT_VENUES.items() if vid != venue and v.actions]
    nearest = min(others, key=lambda vid: travel_ticks(venue, vid))
    return "travel", {"venue": nearest}


class OpenAIAgent(BaseAgent):
    """OpenAI-compatible chat client. Used for OpenRouter (every real model is
    reached through it via ``base_url``)."""

    provider = "openrouter"

    def __init__(
        self,
        agent_id: str,
        model: str,
        *,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__(agent_id, model)
        from openai import AsyncOpenAI

        from app.config import get_settings

        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(settings.agent_timeout_seconds),
            max_retries=0,
        )
        self.max_tokens = settings.max_output_tokens

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        system = render_system_prompt(agent, condition=state.get("_condition", "neutral"))
        user = render_world_brief(state, agent.agent_id)
        gated = bool(state.get("_venue_gating"))
        venue = state.get("_venue") or DEFAULT_VENUE
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=_tools_for_openai(venue, gated=gated),
            # "auto" (not "required"): not every OpenRouter model/provider supports
            # forcing a call. We fall back to "work" below if no tool is returned.
            tool_choice="auto",
            max_tokens=self.max_tokens,
        )
        choice = resp.choices[0]
        monologue = (choice.message.content or "").strip()
        tool_calls = choice.message.tool_calls or []
        if not tool_calls:
            if gated:
                action, arguments = _venue_fallback(None, venue=venue)
                return AgentDecision(
                    action, arguments,
                    monologue=monologue or "(no tool -- walking on)",
                )
            return AgentDecision("work", {}, monologue=monologue or "(no tool -- falling back to work)")

        # Parse all tool calls
        parsed: list[tuple[str, dict]] = []
        for call in tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            parsed.append((call.function.name, args))

        # First = major action
        action, arguments = parsed[0]
        reasoning = arguments.pop("reasoning", "")
        if not monologue and reasoning:
            monologue = reasoning
        wake_after = arguments.pop("wake_after", DEFAULT_WAKE_BEATS)
        wake_if = arguments.pop("wake_if", []) or []

        # Second = optional free action
        free_action = None
        free_arguments: dict = {}
        if len(parsed) >= 2:
            free_action, free_arguments = parsed[1]
            for stripped in ("reasoning", "public_message", "wake_after", "wake_if"):
                free_arguments.pop(stripped, None)

        usage = getattr(resp, "usage", None)
        details = getattr(usage, "completion_tokens_details", None)

        return AgentDecision(
            action=action, arguments=arguments, monologue=monologue,
            free_action=free_action, free_arguments=free_arguments,
            wake_after=_coerce_wake_after(wake_after),
            wake_if=[t for t in wake_if if t in WAKE_TRIGGERS],
            reasoning_tokens=int(getattr(details, "reasoning_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )


def _coerce_wake_after(value: object) -> float:
    """Models sometimes return the sleep length as a string, or as nonsense.

    A bad value must not crash a run, and must not silently become zero either:
    falling back to the default keeps a malformed decision behaving like the old
    turn loop rather than like a hyperactive agent.
    """
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_WAKE_BEATS
