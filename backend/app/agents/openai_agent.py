from __future__ import annotations

import json
import logging

from app.agents.base import AgentDecision, BaseAgent, render_system_prompt, render_world_brief
from app.config import get_settings
from app.models.agent import Agent
from app.oracle.schemas import TOOL_DEFINITIONS

log = logging.getLogger(__name__)


def _tools_for_openai() -> list[dict]:
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
    ]


class OpenAIAgent(BaseAgent):
    """Used for OpenAI, Fireworks (Llama 4), and DeepSeek — all OpenAI-compatible."""

    provider = "openai"

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

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0, max_retries=0)

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        system = render_system_prompt(agent)
        user = render_world_brief(state, agent.agent_id)
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=_tools_for_openai(),
            tool_choice="required",
        )
        choice = resp.choices[0]
        monologue = (choice.message.content or "").strip()
        tool_calls = choice.message.tool_calls or []
        if not tool_calls:
            return AgentDecision("work", {}, monologue=monologue or "(no tool — falling back to work)")
        call = tool_calls[0]
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        # Extract reasoning from tool args if no text monologue was emitted
        reasoning = arguments.pop("reasoning", "")
        if not monologue and reasoning:
            monologue = reasoning
        return AgentDecision(action=call.function.name, arguments=arguments, monologue=monologue)
