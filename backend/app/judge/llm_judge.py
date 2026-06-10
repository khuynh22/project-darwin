"""OpenRouter-backed deception judge. temperature=0 (locked by the spec);
K>1 samples therefore measure provider nondeterminism — exactly what a
reliability run wants. Degrades to a none-verdict on any malformed reply."""

from __future__ import annotations

import json
import logging

from app.judge.base import BaseJudge
from app.judge.context import JudgeContext
from app.judge.prompts import JUDGE_SYSTEM_PROMPT, PROMPT_VERSION, render_judge_user
from app.judge.schemas import DeceptionVerdict, none_verdict, parse_verdict

log = logging.getLogger(__name__)

_VERDICT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_verdict",
        "description": "Record the deception verdict for this agent-turn.",
        "parameters": DeceptionVerdict.model_json_schema(),
    },
}


class LLMJudge(BaseJudge):
    provider = "openrouter"

    def __init__(
        self,
        *,
        judge_model: str,
        api_key: str,
        base_url: str | None = None,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        super().__init__(judge_model=judge_model, prompt_version=prompt_version)
        from openai import AsyncOpenAI

        from app.config import get_settings

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(get_settings().agent_timeout_seconds),
            max_retries=0,
        )

    async def judge(self, ctx: JudgeContext) -> DeceptionVerdict:
        try:
            resp = await self.client.chat.completions.create(
                model=self.judge_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": render_judge_user(ctx)},
                ],
                tools=[_VERDICT_TOOL],
                tool_choice="auto",
            )
        except Exception as exc:  # noqa: BLE001 — a judge failure must not kill the batch
            log.warning("judge call failed for T%s/%s: %s", ctx.turn, ctx.agent_id, exc)
            return none_verdict(f"judge call failed: {exc!s:.200}")

        tool_calls = resp.choices[0].message.tool_calls or []
        if not tool_calls:
            return none_verdict("judge returned no tool call")
        try:
            raw = json.loads(tool_calls[0].function.arguments or "{}")
        except json.JSONDecodeError:
            raw = None
        return parse_verdict(raw)
