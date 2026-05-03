"""Build the runtime agent clients for the seeded roster.

For each spec in AGENT_ROSTER, instantiate the right provider client. If the
required API key is missing OR STUB_MODE is true, fall back to StubAgent so
the simulation still runs end-to-end.
"""
from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.agents.stub import StubAgent
from app.config import AGENT_ROSTER, get_settings

log = logging.getLogger(__name__)


def _build_one(spec: dict) -> BaseAgent:
    settings = get_settings()
    provider = spec["provider"]
    agent_id = spec["agent_id"]

    if settings.stub_mode:
        return StubAgent(agent_id=agent_id, model="stub")

    if provider == "anthropic" and settings.anthropic_api_key:
        from app.agents.anthropic_agent import AnthropicAgent

        return AnthropicAgent(agent_id=agent_id, model=settings.anthropic_model)

    if provider == "openai" and settings.openai_api_key:
        from app.agents.openai_agent import OpenAIAgent

        return OpenAIAgent(agent_id=agent_id, model=settings.openai_model, api_key=settings.openai_api_key)

    if provider == "grok" and settings.grok_api_key:
        from app.agents.openai_agent import OpenAIAgent

        return OpenAIAgent(
            agent_id=agent_id,
            model=settings.grok_model,
            api_key=settings.grok_api_key,
            base_url="https://api.x.ai/v1",
        )

    if provider == "ollama":
        from app.agents.openai_agent import OpenAIAgent

        return OpenAIAgent(
            agent_id=agent_id,
            model=settings.ollama_model,
            api_key="ollama",
            base_url=settings.ollama_base_url + "/v1",
        )

    if provider == "google" and settings.google_api_key:
        from app.agents.google_agent import GoogleAgent

        return GoogleAgent(agent_id=agent_id, model=settings.google_model)

    log.info("Provider %s for %s missing key — using stub", provider, agent_id)
    return StubAgent(agent_id=agent_id, model="stub")


def build_agents() -> dict[str, BaseAgent]:
    return {spec["agent_id"]: _build_one(spec) for spec in AGENT_ROSTER}
