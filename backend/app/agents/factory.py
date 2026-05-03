"""Build the runtime agent clients for the seeded roster.

For each spec in AGENT_ROSTER (or a dynamic roster), instantiate the right
provider client. If the required API key is missing OR STUB_MODE is true,
fall back to StubAgent so the simulation still runs end-to-end.
"""
from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.agents.stub import StubAgent
from app.config import AGENT_ROSTER, get_settings

log = logging.getLogger(__name__)


def _build_one(spec: dict, api_key: str | None = None) -> BaseAgent:
    """Build a single agent client from a roster spec.

    If *api_key* is provided (dynamic roster), it overrides the global settings key.
    """
    settings = get_settings()
    provider = spec["provider"]
    agent_id = spec["agent_id"]
    model = spec.get("model")  # dynamic roster can specify model

    if settings.stub_mode:
        return StubAgent(agent_id=agent_id, model="stub")

    if provider == "anthropic":
        key = api_key or settings.anthropic_api_key
        if key:
            from app.agents.anthropic_agent import AnthropicAgent
            return AnthropicAgent(agent_id=agent_id, model=model or settings.anthropic_model, api_key=key)

    elif provider == "openai":
        key = api_key or settings.openai_api_key
        if key:
            from app.agents.openai_agent import OpenAIAgent
            return OpenAIAgent(agent_id=agent_id, model=model or settings.openai_model, api_key=key)

    elif provider == "grok":
        key = api_key or settings.grok_api_key
        if key:
            from app.agents.openai_agent import OpenAIAgent
            return OpenAIAgent(
                agent_id=agent_id, model=model or settings.grok_model,
                api_key=key, base_url="https://api.x.ai/v1",
            )

    elif provider == "ollama":
        from app.agents.openai_agent import OpenAIAgent
        return OpenAIAgent(
            agent_id=agent_id, model=model or settings.ollama_model,
            api_key="ollama", base_url=settings.ollama_base_url + "/v1",
        )

    elif provider == "google":
        key = api_key or settings.google_api_key
        if key:
            from app.agents.google_agent import GoogleAgent
            return GoogleAgent(agent_id=agent_id, model=model or settings.google_model, api_key=key)

    log.info("Provider %s for %s missing key -- using stub", provider, agent_id)
    return StubAgent(agent_id=agent_id, model="stub")


def build_agents(roster: list[dict] | None = None) -> dict[str, BaseAgent]:
    """Build all agent clients.

    If *roster* is provided (from dynamic configuration), each entry may include
    an ``api_key`` field used instead of the global settings key.
    """
    specs = roster or AGENT_ROSTER
    result: dict[str, BaseAgent] = {}
    for spec in specs:
        per_agent_key = spec.get("api_key")
        result[spec["agent_id"]] = _build_one(spec, api_key=per_agent_key)
    return result
