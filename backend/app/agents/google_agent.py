from __future__ import annotations

import logging

from app.agents.base import AgentDecision, BaseAgent, render_system_prompt, render_world_brief
from app.config import get_settings
from app.models.agent import Agent
from app.oracle.schemas import TOOL_DEFINITIONS

log = logging.getLogger(__name__)


_UNSUPPORTED_KEYS = {"exclusiveMinimum", "exclusiveMaximum", "$defs", "additionalProperties"}


def _clean_schema(schema: dict) -> dict:
    """Uppercase types and strip JSON-schema keys Google doesn't support."""
    out = {}
    for k, v in schema.items():
        if k in _UNSUPPORTED_KEYS:
            continue
        if k == "type" and isinstance(v, str):
            out[k] = v.upper()
        elif isinstance(v, dict):
            out[k] = _clean_schema(v)
        elif isinstance(v, list):
            out[k] = [_clean_schema(i) if isinstance(i, dict) else i for i in v]
        else:
            out[k] = v
    return out


def _tools_for_google() -> list:
    from google.genai import types

    decls = []
    for t in TOOL_DEFINITIONS:
        params = _clean_schema(t["parameters"])
        decls.append(types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=params,
        ))
    return [types.Tool(function_declarations=decls)]


class GoogleAgent(BaseAgent):
    provider = "google"

    def __init__(self, agent_id: str, model: str) -> None:
        super().__init__(agent_id, model)
        from google import genai

        self.client = genai.Client(api_key=get_settings().google_api_key)

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        system = render_system_prompt(agent)
        user = render_world_brief(state, agent.agent_id)
        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[user],
            config={
                "system_instruction": system,
                "tools": _tools_for_google(),
                "tool_config": {"function_calling_config": {"mode": "ANY"}},
            },
        )
        monologue_parts: list[str] = []
        action = "work"
        arguments: dict = {}
        for cand in resp.candidates or []:
            for part in (cand.content.parts or []):
                if getattr(part, "text", None):
                    monologue_parts.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc and fc.name:
                    action = fc.name
                    arguments = dict(fc.args or {})
                    break
            if action != "work" or arguments:
                break
        return AgentDecision(action=action, arguments=arguments, monologue="\n".join(monologue_parts).strip())
