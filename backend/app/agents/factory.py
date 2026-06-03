"""Build the runtime agent clients for a roster.

Every real agent is reached through **OpenRouter** — a single OpenAI-compatible
gateway to models from every provider. Users bring their own OpenRouter key per
session and pick any model id (e.g. "anthropic/claude-opus-4.7", "openai/gpt-5").

The ``stub`` provider is internal only (tests / CLI dry-runs); it is never
offered in the UI. If a real agent has no key available the factory falls back
to a stub so the turn loop never crashes — but `configure` validates keys up
front, so that path effectively only happens for keyless CLI runs.
"""
from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.agents.stub import StubAgent
from app.config import AGENT_ROSTER, get_settings

log = logging.getLogger(__name__)


def _build_one(spec: dict, api_key: str | None = None) -> BaseAgent:
    """Build a single agent client from a roster spec.

    *api_key* (when present) is the session's OpenRouter key.
    """
    settings = get_settings()
    provider = spec.get("provider", "openrouter")
    agent_id = spec["agent_id"]
    model = spec.get("model") or settings.openrouter_model

    if provider == "stub":
        return StubAgent(agent_id=agent_id, model="stub")

    # Everything else routes through OpenRouter.
    key = api_key or settings.openrouter_api_key
    if key:
        from app.agents.openai_agent import OpenAIAgent

        return OpenAIAgent(
            agent_id=agent_id,
            model=model,
            api_key=key,
            base_url=settings.openrouter_base_url,
        )

    log.info("OpenRouter key missing for %s -- using stub", agent_id)
    return StubAgent(agent_id=agent_id, model="stub")


def build_agents(roster: list[dict] | None = None) -> dict[str, BaseAgent]:
    """Build all agent clients.

    Each roster entry may include an ``api_key`` (the session's OpenRouter key).
    """
    specs = roster or AGENT_ROSTER
    result: dict[str, BaseAgent] = {}
    for spec in specs:
        per_agent_key = spec.get("api_key")
        result[spec["agent_id"]] = _build_one(spec, api_key=per_agent_key)
    return result
