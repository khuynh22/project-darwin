"""Compute structural metrics for a Project Darwin session and write a report.

Usage:
    python -m scripts.compute_metrics --session cli --out metrics.json [--csv series.csv]

Reads the persisted rows for one session and emits a JSON metric report (plus an
optional per-turn CSV for plotting). All metrics are structural / deterministic.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import CLI_SESSION_ID  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.metrics import compute_metrics  # noqa: E402

_CATS = ["economic", "prosocial", "aggressive", "manipulative", "other"]


def _write_csv(report: dict, path: Path) -> None:
    gini_by_turn = {p["turn"]: p for p in report["gini_over_time"]}
    mix_by_turn = {p["turn"]: p for p in report["action_mix_over_time"]}
    dec_by_turn = {p["turn"]: p["count"] for p in report["deception"]["over_time"]}
    turns = sorted(set(gini_by_turn) | set(mix_by_turn))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["turn", "gini", "alive", *_CATS, "deception"])
        for t in turns:
            g = gini_by_turn.get(t, {})
            m = mix_by_turn.get(t, {})
            w.writerow(
                [t, g.get("gini", ""), g.get("alive", ""), *[m.get(c, 0) for c in _CATS], dec_by_turn.get(t, 0)]
            )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=CLI_SESSION_ID)
    parser.add_argument("--out", type=Path, default=Path("metrics.json"))
    parser.add_argument("--csv", type=Path, default=None, help="Optional per-turn CSV for plotting.")
    args = parser.parse_args()

    async with SessionLocal() as session:
        report = await compute_metrics(session, args.session)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if args.csv:
        _write_csv(report, args.csv)

    d = report
    print(
        f"[metrics] session={d['session_id']} turns={d['turns']} "
        f"agents={d['n_agents']} survivors={d['survivors']}"
    )
    print(f"  winner={d['winner']} apex_turn={d['apex_turn']} final_gini={d['final_gini']}")
    print(f"  action_mix={d['action_mix']}")
    print(
        f"  deception: events={d['deception']['events']} rate={d['deception']['rate']} "
        f"acts/turn={d['deception']['acts_per_turn']} by_action={d['deception']['by_action']}"
    )
    print(
        f"  betrayals={d['betrayal_count']} median_delay={d['betrayal_median_delay']} "
        f"bluff_mismatch={d['bluff_mismatch']}"
    )
    print(f"  per_model={d['per_model']}")
    print(f"[metrics] wrote {args.out}" + (f" + {args.csv}" if args.csv else ""))


if __name__ == "__main__":
    asyncio.run(main())
