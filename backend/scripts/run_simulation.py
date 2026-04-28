"""Run a Project Darwin simulation and export thought logs for research.

Usage:
    python -m scripts.run_simulation --turns 100 --out thought_logs/run-001.jsonl

Honors STUB_MODE from .env so it works without API keys.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure `app` is importable when invoked as `python -m scripts.run_simulation`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.agents.factory import build_agents  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.ledger import ThoughtLog, Transaction, WorldEvent  # noqa: E402
from app.oracle.engine import run_turn, seed_roster  # noqa: E402


async def _export_thoughts(out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    async with SessionLocal() as session:
        thoughts = (await session.execute(select(ThoughtLog).order_by(ThoughtLog.id))).scalars().all()
        with out_path.open("w", encoding="utf-8") as f:
            for t in thoughts:
                f.write(
                    json.dumps(
                        {
                            "turn": t.turn,
                            "agent_id": t.agent_id,
                            "monologue": t.monologue,
                            "action": t.action,
                            "arguments": t.arguments,
                            "outcome": t.outcome,
                        }
                    )
                    + "\n"
                )
                count += 1
    return count


async def _print_summary() -> None:
    async with SessionLocal() as session:
        agents = (await session.execute(select(Agent).order_by(Agent.balance.desc()))).scalars().all()
        events = (await session.execute(select(WorldEvent))).scalars().all()
        tx_count = (await session.execute(select(Transaction))).scalars().all()
    print("\n=== FINAL STANDINGS ===")
    for a in agents:
        status = "ALIVE" if a.alive else f"ELIM@T{a.eliminated_at_turn}"
        spouse = f" married->{a.spouse_id}" if a.spouse_id else ""
        print(f"  {a.display_name:8} ${a.balance:7.2f}  {status}{spouse}")
    print(f"\nTotal events: {len(events)}, transactions: {len(tx_count)}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path("thought_logs/latest.jsonl"))
    parser.add_argument("--reset", action="store_true", help="Reset DB before running.")
    args = parser.parse_args()

    settings = get_settings()
    print(f"[darwin] starting sim -- {args.turns} turns, stub_mode={settings.stub_mode}")

    await init_db()
    async with SessionLocal() as session:
        if args.reset:
            from app.db import Base, engine

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        await seed_roster(session)

    agents = build_agents()

    for turn in range(1, args.turns + 1):
        async with SessionLocal() as session:
            result = await run_turn(session, turn=turn, agents=agents)
        if result.eliminated:
            print(f"  T{turn}: eliminated -> {result.eliminated}")
        if result.apex_declared:
            print(f"  T{turn}: APEX DECLARED -> {result.apex_declared}")
            break
        if turn % 10 == 0:
            print(f"  T{turn}: cycle settled")

    written = await _export_thoughts(args.out)
    print(f"[darwin] wrote {written} thought rows -> {args.out}")
    await _print_summary()


if __name__ == "__main__":
    asyncio.run(main())
