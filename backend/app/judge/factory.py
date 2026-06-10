"""Build a judge. Mirrors agents/factory.py: ``provider="stub"`` or a missing
key falls back to StubJudge — never raises."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.judge.base import BaseJudge
from app.judge.stub_judge import StubJudge

log = logging.getLogger(__name__)


def build_judge(
    *,
    provider: str = "openrouter",
    judge_model: str | None = None,
    api_key: str | None = None,
) -> BaseJudge:
    settings = get_settings()
    if provider == "stub":
        return StubJudge()

    key = api_key or settings.openrouter_api_key
    if key:
        from app.judge.llm_judge import LLMJudge

        return LLMJudge(
            judge_model=judge_model or settings.judge_model,
            api_key=key,
            base_url=settings.openrouter_base_url,
        )

    log.info("OpenRouter key missing for judge -- using StubJudge")
    return StubJudge()
