from __future__ import annotations

import json
import logging

from app.agents.base import AgentDecision, BaseAgent, render_system_prompt, render_world_brief
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

        # Second = optional free action
        free_action = None
        free_arguments: dict = {}
        if len(parsed) >= 2:
            free_action, free_arguments = parsed[1]
            free_arguments.pop("reasoning", None)
            free_arguments.pop("public_message", None)

        return AgentDecision(
            action=action, arguments=arguments, monologue=monologue,
            free_action=free_action, free_arguments=free_arguments,
        )
