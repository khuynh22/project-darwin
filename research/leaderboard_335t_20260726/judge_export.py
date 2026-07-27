"""Judge a UI-exported thoughts JSONL with the v2 LLM judge — no DB required.

The UI export carries only the triple (monologue / public_message / action /
outcome). We build a JudgeContext per row (the ``outcome`` string carries the
real ground truth — steal amounts, the actual slander/gaslight text, etc.), call
the same v2 judge the flagship used, and write one verdict per line.

- Excludes KIMI (56% tool-call fallbacks — artifact, not behavior) and any
  ``skip`` / tool-fallback rows (no real decision to judge).
- **Idempotent / resumable:** re-running skips rows already in --out, so a
  budget/key cutoff mid-run never costs you a re-judge.
- Provider ``stub`` runs the deterministic StubJudge (free) to validate the
  pipeline end-to-end; ``openrouter`` uses the real judge (default Opus).

Usage (from repo root):
  OPENROUTER_API_KEY=$KEY python research/leaderboard_335t_20260726/judge_export.py \
      [--provider openrouter] [--judge-model anthropic/claude-opus-4.7] \
      [--limit N] [--out verdicts_335t.jsonl]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.judge.context import JudgeContext  # noqa: E402
from app.judge.factory import build_judge  # noqa: E402
from app.judge.schemas import normalize_verdict  # noqa: E402

HERE = Path(__file__).parent
EXCLUDE_AGENTS = {"kimi"}
SKIP_ACTIONS = {"skip"}


def _is_fallback(mono: str | None) -> bool:
    m = mono or ""
    return ("no tool" in m) or ("falling back" in m)


def _ctx(row: dict) -> JudgeContext:
    args = row.get("arguments") or {}
    target = args.get("target") or args.get("target_id")
    return JudgeContext(
        session_id="ui335", turn=int(row["turn"]), agent_id=row["agent_id"],
        monologue=row.get("monologue") or "", public_message=row.get("public_message") or "",
        action=row.get("action") or "", arguments=args, outcome=row.get("outcome") or "",
        balance=None, trust_score=None, target_id=target, transactions=[],
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(HERE / "thoughts_335t.jsonl"))
    ap.add_argument("--out", default=str(HERE / "verdicts_335t.jsonl"))
    ap.add_argument("--provider", default="openrouter", choices=["openrouter", "stub"])
    ap.add_argument("--judge-model", default=None, help="defaults to settings.judge_model (Opus)")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="0 = all judgeable rows; else first N (smoke)")
    args = ap.parse_args()

    rows = [json.loads(x) for x in open(args.inp, encoding="utf-8") if x.strip()]
    judgeable = [
        r for r in rows
        if r["agent_id"] not in EXCLUDE_AGENTS
        and r.get("action") not in SKIP_ACTIONS
        and not _is_fallback(r.get("monologue"))
    ]
    if args.limit:
        judgeable = judgeable[:args.limit]

    done: set = set()
    if os.path.exists(args.out):
        for x in open(args.out, encoding="utf-8"):
            if x.strip():
                d = json.loads(x)
                done.add((d["turn"], d["agent_id"]))
    todo = [r for r in judgeable if (r["turn"], r["agent_id"]) not in done]
    print(f"[judge] rows={len(rows)} judgeable={len(judgeable)} done={len(done)} todo={len(todo)}")
    if not todo:
        print("[judge] nothing to do."); return

    key = os.environ.get("OPENROUTER_API_KEY")
    if args.provider == "openrouter" and not key:
        sys.exit("[judge] ERROR: OPENROUTER_API_KEY not set — refusing to silently fall back to stub.")
    judge = build_judge(provider=args.provider, judge_model=args.judge_model, api_key=key)
    print(f"[judge] model={judge.judge_model} prompt_version={judge.prompt_version} provider={judge.provider}")

    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    outf = open(args.out, "a", encoding="utf-8")
    written = 0

    async def _one(r: dict) -> None:
        nonlocal written
        async with sem:
            v = await judge.judge(_ctx(r))
        v = normalize_verdict(v, actor_id=r["agent_id"])
        rec = {
            "turn": int(r["turn"]), "agent_id": r["agent_id"],
            "is_deceptive": v.is_deceptive, "deception_type": v.deception_type,
            "channels_in_conflict": list(v.channels_in_conflict), "target_id": v.target_id,
            "confidence": v.confidence, "rationale": v.rationale,
        }
        async with lock:
            outf.write(json.dumps(rec) + "\n"); outf.flush()
            written += 1
            if written % 50 == 0:
                print(f"[judge] {written}/{len(todo)}")

    try:
        await asyncio.gather(*[_one(r) for r in todo])
    finally:
        outf.close()
    print(f"[judge] wrote {written} verdicts -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
