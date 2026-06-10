"""Batch-judge a Project Darwin session for intent-grounded deception.

Usage:
    python -m scripts.judge_deception --session cli [--provider stub|openrouter]
        [--judge-model anthropic/claude-opus-4.7] [--samples 1]

Offline batch over persisted rows. Verdicts are cached in deception_judgments
keyed by (session, turn, agent, judge_model, prompt_version, sample_idx) —
re-running with the same key overwrites; a new model/version/K coexists.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import CLI_SESSION_ID  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.judge.factory import build_judge  # noqa: E402
from app.judge.runner import judge_session  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=CLI_SESSION_ID)
    parser.add_argument("--provider", default="openrouter", choices=["stub", "openrouter"])
    parser.add_argument("--judge-model", default=None, help="Defaults to settings.judge_model.")
    parser.add_argument("--samples", type=int, default=1, help="K verdicts per agent-turn.")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()

    await init_db()
    judge = build_judge(provider=args.provider, judge_model=args.judge_model)
    print(
        f"[judge] session={args.session} judge={judge.judge_model} "
        f"prompt={judge.prompt_version} K={args.samples}"
    )
    async with SessionLocal() as session:
        written = await judge_session(
            session, args.session, judge,
            samples=args.samples, concurrency=args.concurrency,
        )
    print(f"[judge] wrote {written} verdict rows")


if __name__ == "__main__":
    asyncio.run(main())
