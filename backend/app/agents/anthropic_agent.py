from __future__ import annotations

import json
import logging

from app.agents.base import AgentDecision, BaseAgent, render_system_prompt, render_world_brief
from app.config import get_settings
from app.models.agent import Agent
from app.oracle.schemas import TOOL_DEFINITIONS

log = logging.getLogger(__name__)


def _tools_for_anthropic() -> list[dict]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in TOOL_DEFINITIONS
    ]


class AnthropicAgent(BaseAgent):
    provider = "anthropic"

    def __init__(self, agent_id: str, model: str) -> None:
        super().__init__(agent_id, model)
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        system = render_system_prompt(agent)
        user = render_world_brief(state, agent.agent_id)
        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            tools=_tools_for_anthropic(),
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": user}],
        )
        monologue_parts: list[str] = []
        action = "work"
        arguments: dict = {}
        for block in msg.content:
            if block.type == "text":
                monologue_parts.append(block.text)
            elif block.type == "tool_use":
                action = block.name
                arguments = dict(block.input or {})
                break
        return AgentDecision(action=action, arguments=arguments, monologue="\n".join(monologue_parts).strip(),
                             raw={"stop_reason": msg.stop_reason})
