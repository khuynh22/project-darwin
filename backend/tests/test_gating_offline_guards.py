"""Nothing offline can honour venue gating yet, so nothing may pretend to.

Every offline entry point drives ``run_turn``, which offers every action wherever
the agent stands. Read a gated trace through one of them and the run silently
becomes a different experiment: for ``probe/replay.py`` that means a live seat
model facing the full catalogue while its divergence accounting compares it
against gated recorded behaviour. Each reader of a ``RunManifest`` therefore says
so, loudly, before it executes anything.
"""

from __future__ import annotations

import json

import pytest

from app.probe.mine import mine_probes
from app.trace.io import TraceWriter
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    RunManifest,
    TurnRecord,
    TurnState,
)
from app.trace.validate import validate_trace


def _trace(path, *, venue_gating: bool):
    manifest = RunManifest(
        kind="run",
        schema_version=6,
        run_id="r",
        env=EnvManifest(name="darwin", seed=3),
        horizon=6,
        venue_gating=venue_gating,
        agents=[
            AgentManifest(agent_id="red", turns_alive=6, specialty="food"),
            AgentManifest(agent_id="blue", turns_alive=6, specialty="ore"),
        ],
    )
    with TraceWriter(path, manifest) as w:
        for turn in range(1, 4):
            for agent in ("red", "blue"):
                w.append(
                    TurnRecord(
                        kind="turn",
                        turn=turn,
                        agent_id=agent,
                        action="slander" if (agent == "red" and turn == 2) else "work",
                        arguments={"target": "blue"} if turn == 2 else {},
                        monologue="m",
                        public_message="p",
                        state=TurnState(
                            balance=4.0, trust_score=50.0, alive=["red", "blue"]
                        ),
                    )
                )
    return path


def _verdicts(path):
    row = {
        "turn": 2,
        "agent_id": "red",
        "is_deceptive": True,
        "deception_type": "false_state_claim",
        "target_id": "blue",
        "confidence": 0.9,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


def test_mining_refuses_a_gated_trace(tmp_path):
    trace = _trace(tmp_path / "gated.jsonl", venue_gating=True)
    verdicts = _verdicts(tmp_path / "v.jsonl")

    with pytest.raises(ValueError, match="venue gating"):
        mine_probes(trace, verdicts)


def test_mining_still_accepts_an_ungated_trace(tmp_path):
    trace = _trace(tmp_path / "plain.jsonl", venue_gating=False)
    verdicts = _verdicts(tmp_path / "v.jsonl")

    assert mine_probes(trace, verdicts)


async def test_reexecute_refuses_a_gated_trace(tmp_path):
    from app.replay.reexecute import reexecute

    trace = _trace(tmp_path / "gated.jsonl", venue_gating=True)

    def _no_session():  # pragma: no cover - the guard must return first
        raise AssertionError("reexecute opened a session for a gated trace")

    report = await reexecute(trace, tmp_path / "cache", _no_session)

    assert not report.ok
    assert "VenueGatingUnsupported" in report.error
    assert report.turns == 0


def test_validation_warns_about_a_gated_trace_without_failing_it(tmp_path):
    gated = validate_trace(_trace(tmp_path / "gated.jsonl", venue_gating=True))
    plain = validate_trace(_trace(tmp_path / "plain.jsonl", venue_gating=False))

    assert gated.ok, gated.errors
    assert any("venue gating" in w for w in gated.warnings)
    assert plain.warnings == []
