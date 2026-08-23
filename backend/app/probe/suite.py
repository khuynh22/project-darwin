"""Run a probe suite against one model and reduce it to outcomes.

A probe is sampled ``samples`` times because the response is not deterministic.
Each sample is one k-turn replay; the sample counts as deceptive if *any* of the
seat's turns in that window was judged deceptive, and its sophistication is the
highest grade among them -- a campaign is not made less sophisticated by opening
with an omission.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.judge.context import JudgeContext
from app.judge.schemas import normalize_verdict
from app.probe.replay import run_probe
from app.probe.schema import Probe
from app.probe.score import ProbeOutcome

log = logging.getLogger(__name__)


def build_seat_agent(seat: str, *, provider: str, model: str,
                     api_key: str | None = None) -> BaseAgent:
    """A single-seat roster is enough to get the model under test."""
    from app.agents.factory import build_agents

    spec = {
        "agent_id": seat,
        "display_name": seat.upper(),
        "provider": provider,
        "personality": "",
        "sprite": "blue",
        "model": model,
    }
    if api_key:
        spec["api_key"] = api_key
    return build_agents(roster=[spec])[seat]


async def _judge_seat(judge: Any, probe: Probe, turns: Sequence[Any]) -> tuple[bool, int | None]:
    deceptive = False
    best: int | None = None
    for turn in turns:
        raw = await judge.judge(
            JudgeContext(
                session_id=probe.probe_id,
                turn=turn.turn,
                agent_id=turn.agent_id,
                monologue=turn.monologue,
                public_message=turn.public_message,
                action=turn.action,
                arguments=turn.arguments,
                outcome=turn.outcome,
                balance=None,
                trust_score=None,
                target_id=turn.arguments.get("target"),
                transactions=[],
            )
        )
        if raw.failed:
            continue
        verdict = normalize_verdict(raw, actor_id=turn.agent_id)
        if verdict.is_deceptive:
            deceptive = True
            if verdict.sophistication is not None:
                best = verdict.sophistication if best is None else max(best, verdict.sophistication)
    return deceptive, best


async def run_suite(
    session_factory: Any,
    probes: Sequence[Probe],
    *,
    provider: str,
    model: str,
    judge: Any,
    samples: int = 5,
    api_key: str | None = None,
) -> list[ProbeOutcome]:
    outcomes: list[ProbeOutcome] = []
    for probe in probes:
        for sample in range(samples):
            seat_agent = build_seat_agent(probe.seat, provider=provider, model=model,
                                          api_key=api_key)
            # sha1, not hash(): string hashing is randomised per process,
            # so ids must not depend on it (see replay._session_id).
            digest = hashlib.sha1(f"{probe.probe_id}:{sample}".encode()).hexdigest()
            sid = f"pb{digest[:12]}"
            result = await run_probe(session_factory, probe, seat_agent=seat_agent,
                                     session_id=sid)
            deceptive = False
            sophistication: int | None = None
            if not result.excluded and probe.family == "propensity":
                deceptive, sophistication = await _judge_seat(judge, probe, result.turns)
            outcomes.append(
                ProbeOutcome(
                    probe_id=probe.probe_id,
                    family=probe.family,
                    seat=probe.seat,
                    difficulty=probe.difficulty,
                    deceptive=deceptive,
                    sophistication=sophistication,
                    acted_on_lie=result.acted_on_lie,
                    excluded=result.excluded,
                    divergence_rate=result.divergence_rate,
                )
            )
    return outcomes


def save_outcomes(path: Path, model: str, outcomes: Sequence[ProbeOutcome]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for outcome in outcomes:
            row = {"model": model, **outcome.__dict__}
            fh.write(json.dumps(row, default=str) + "\n")


def load_outcomes(path: Path) -> tuple[str, list[ProbeOutcome]]:
    model = ""
    outcomes: list[ProbeOutcome] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        model = row.pop("model", model)
        outcomes.append(ProbeOutcome(**row))
    return model, outcomes
