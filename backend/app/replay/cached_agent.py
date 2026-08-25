"""An agent that answers from a recorded cache instead of a provider."""

from __future__ import annotations

import logging

from app.agents.base import AgentDecision, BaseAgent, render_system_prompt, render_world_brief
from app.models.agent import Agent
from app.replay.cache import CacheMiss, ResponseCache, decision_key

log = logging.getLogger(__name__)

Mode = str  # "strict" | "permissive"


class CachedAgent(BaseAgent):
    """Wraps an agent, serving recorded decisions when the world matches.

    ``strict`` is the mode that makes reproduction meaningful: a miss raises
    rather than silently falling through to a live call, so a run that does not
    reproduce fails loudly instead of quietly becoming a new experiment.
    ``permissive`` records misses and is how a cache gets built in the first
    place.
    """

    provider = "cached"

    def __init__(
        self,
        agent_id: str,
        *,
        cache: ResponseCache,
        inner: BaseAgent | None = None,
        mode: Mode = "strict",
        model: str = "",
        prompt_version: str = "",
        temperature: float = 0.0,
    ) -> None:
        self.agent_id = agent_id
        self.cache = cache
        self.inner = inner
        self.mode = mode
        self.model = model or getattr(inner, "model", "") or ""
        self.prompt_version = prompt_version
        self.temperature = temperature

    def _key(self, state: dict, agent: Agent) -> str:
        return decision_key(
            env_version=self.cache.env_version,
            model=self.model,
            prompt_version=self.prompt_version,
            system_prompt=render_system_prompt(
                agent, condition=state.get("_condition", "neutral")
            ),
            user_prompt=render_world_brief(state, agent.agent_id),
            tool_names=[],
            temperature=self.temperature,
        )

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        key = self._key(state, agent)
        recorded = self.cache.get(key)
        if recorded is not None:
            return AgentDecision(
                action=recorded["action"],
                arguments=dict(recorded.get("arguments") or {}),
                monologue=recorded.get("monologue", ""),
                free_action=recorded.get("free_action"),
                free_arguments=dict(recorded.get("free_arguments") or {}),
                raw=dict(recorded.get("raw") or {}),
            )

        if self.mode == "strict" or self.inner is None:
            raise CacheMiss(
                f"no recorded decision for {agent.agent_id} at turn "
                f"{state.get('turn')} (key {key[:12]})"
            )

        decision = await self.inner.decide(state, agent)
        self.cache.put(key, _as_row(decision))
        return decision


def _as_row(decision: AgentDecision) -> dict:
    return {
        "action": decision.action,
        "arguments": decision.arguments,
        "monologue": decision.monologue,
        "free_action": decision.free_action,
        "free_arguments": decision.free_arguments,
        "raw": decision.raw,
    }
