"""``darwin`` -- validate, upgrade, and read traces from any directory.

Subcommands that need the environment or a provider key arrive with the sweep
and probe plans; everything here runs offline against files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.trace.adapters.legacy_jsonl import upgrade_legacy_jsonl
from app.trace.io import TraceWriter, read_trace
from app.trace.validate import validate_trace

_SPAN = 200


def _cmd_validate(args: argparse.Namespace) -> int:
    report = validate_trace(Path(args.path))
    if report.ok:
        print(f"ok: {args.path} ({report.n_turns} turns)")
        return 0
    print(f"invalid: {args.path}")
    for error in report.errors:
        print(f"  {error}")
    return 1


def _cmd_upgrade(args: argparse.Namespace) -> int:
    models = json.loads(Path(args.models).read_text(encoding="utf-8")) if args.models else {}
    exclude = set(args.exclude.split(",")) if args.exclude else None
    manifest, turns = upgrade_legacy_jsonl(
        Path(args.src),
        run_id=args.run_id,
        models=models,
        condition=args.condition,
        seed=args.seed,
        exclude=exclude,
    )
    with TraceWriter(Path(args.out), manifest) as writer:
        for turn in turns:
            writer.append(turn)
    print(f"wrote {args.out}: {len(turns)} turns, {len(manifest.agents)} agents")
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    manifest, turns = read_trace(Path(args.path))
    print(f"{manifest.run_id}  condition={manifest.condition}  horizon={manifest.horizon}")
    for turn in turns:
        if args.agent and turn.agent_id != args.agent:
            continue
        print(f"\nt{turn.turn:>4} {turn.agent_id}  [{turn.action}]  {turn.outcome}")
        if turn.monologue:
            print(f"  private: {turn.monologue[:_SPAN]}")
        if turn.public_message:
            print(f"  public : {turn.public_message[:_SPAN]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="darwin", description="Darwin measurement harness")
    sub = parser.add_subparsers(dest="command")

    p_validate = sub.add_parser("validate", help="check a trace against schema v4")
    p_validate.add_argument("path")
    p_validate.set_defaults(func=_cmd_validate)

    p_upgrade = sub.add_parser("upgrade", help="convert a legacy v2/v3 export to v4")
    p_upgrade.add_argument("src")
    p_upgrade.add_argument("--out", required=True)
    p_upgrade.add_argument("--run-id", required=True)
    p_upgrade.add_argument("--models", help="JSON file mapping agent_id -> model string")
    p_upgrade.add_argument("--condition", default="neutral")
    p_upgrade.add_argument("--seed", type=int, default=0)
    p_upgrade.add_argument("--exclude", help="comma-separated agent ids to drop")
    p_upgrade.set_defaults(func=_cmd_upgrade)

    p_replay = sub.add_parser("replay", help="print a trace turn by turn")
    p_replay.add_argument("path")
    p_replay.add_argument("--agent", help="only this agent")
    p_replay.set_defaults(func=_cmd_replay)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
