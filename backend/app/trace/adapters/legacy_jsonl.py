"""Upgrade a v2/v3 Darwin export to schema v4.

The legacy exports carry only the triple. Lifespans are recovered as each
agent's last observed turn, and per-turn world state is unavailable, so the
manifest is marked ``state_fidelity="partial"`` -- probe mining must not assume
inventory or social state from these files.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    Instrument,
    RunManifest,
    TurnRecord,
)

_FALLBACK_MARKERS = ("no tool", "falling back")


def is_fallback(monologue: str | None) -> bool:
    """True when the monologue shows the provider returned no usable tool call.

    Kept as one function because the same sniff was duplicated in
    ``judge_export.py`` and ``analyze_coherence.py``; its result belongs in
    ``instrument.tool_call_ok`` so downstream code filters on data, not on a
    hardcoded agent name.
    """
    text = (monologue or "").lower()
    return any(marker in text for marker in _FALLBACK_MARKERS)


def upgrade_legacy_jsonl(
    src: Path,
    *,
    run_id: str,
    models: dict[str, str],
    condition: str = "neutral",
    seed: int = 0,
    exclude: set[str] | None = None,
) -> tuple[RunManifest, list[TurnRecord]]:
    excluded = exclude or set()
    turns: list[TurnRecord] = []
    last_turn: dict[str, int] = {}

    with Path(src).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            agent_id = row.get("agent_id")
            if not agent_id or agent_id in excluded:
                continue
            turn = int(row["turn"])
            last_turn[agent_id] = max(last_turn.get(agent_id, 0), turn)
            turns.append(
                TurnRecord(
                    kind="turn",
                    turn=turn,
                    agent_id=agent_id,
                    monologue=row.get("monologue") or "",
                    public_message=row.get("public_message") or "",
                    action=row.get("action") or "",
                    arguments=row.get("arguments") or {},
                    outcome=row.get("outcome") or "",
                    instrument=Instrument(tool_call_ok=not is_fallback(row.get("monologue"))),
                )
            )

    manifest = RunManifest(
        kind="run",
        schema_version=4,
        run_id=run_id,
        env=EnvManifest(name="darwin", seed=seed),
        condition=condition,
        horizon=max(last_turn.values(), default=0),
        state_fidelity="partial",
        agents=[
            AgentManifest(
                agent_id=agent_id,
                model=models.get(agent_id, ""),
                provider="openrouter" if models.get(agent_id) else "",
                turns_alive=alive,
            )
            for agent_id, alive in sorted(last_turn.items())
        ],
    )
    return manifest, turns
