from __future__ import annotations

import abc

from app.judge.context import JudgeContext
from app.judge.schemas import DeceptionVerdict


class BaseJudge(abc.ABC):
    """Provider-agnostic deception judge."""

    provider: str = "base"

    def __init__(self, *, judge_model: str, prompt_version: str) -> None:
        self.judge_model = judge_model
        self.prompt_version = prompt_version

    @abc.abstractmethod
    async def judge(self, ctx: JudgeContext) -> DeceptionVerdict: ...
