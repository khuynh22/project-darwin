from __future__ import annotations

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

    def __init__(self, agent_id: str, model: str, api_key: str | None = None) -> None:
        super().__init__(agent_id, model)
        from anthropic import AsyncAnthropic

        key = api_key or get_settings().anthropic_api_key
        self.client = AsyncAnthropic(api_key=key, timeout=120.0)

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
        tool_calls: list[tuple[str, dict]] = []
        for block in msg.content:
            if block.type == "text":
                monologue_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append((block.name, dict(block.input or {})))

        # First tool call = major action, second = optional free action
        action = "work"
        arguments: dict = {}
        free_action = None
        free_arguments: dict = {}

        if tool_calls:
            action, arguments = tool_calls[0]
        if len(tool_calls) >= 2:
            free_action, free_arguments = tool_calls[1]
            free_arguments.pop("reasoning", None)
            free_arguments.pop("public_message", None)

        reasoning = arguments.pop("reasoning", "")
        if not monologue_parts and reasoning:
            monologue_parts.append(reasoning)

        return AgentDecision(
            action=action, arguments=arguments,
            monologue="\n".join(monologue_parts).strip(),
            raw={"stop_reason": msg.stop_reason},
            free_action=free_action, free_arguments=free_arguments,
        )
