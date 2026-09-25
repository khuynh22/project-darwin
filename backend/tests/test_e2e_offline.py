"""Run the whole pipeline offline: simulate, export, validate, judge, measure.

No network, no API key. This is the reproducibility claim in executable form --
a reviewer who can run pytest can run the harness.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.judge.context import JudgeContext
from app.judge.factory import build_judge
from app.judge.schemas import normalize_verdict
from app.measure import bh_correct, coherence_metrics, permutation_null
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.oracle.engine import run_turn, seed_roster
from app.trace.adapters.darwin_db import export_session
from app.trace.io import TraceWriter, read_trace
from app.trace.validate import validate_trace

SID = "e2e"
TURNS = 12


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(4)
    ]


async def test_offline_pipeline(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, SID, _roster(), seed=11)
        agents = build_agents(roster=_roster())
        for turn in range(1, TURNS + 1):
            await run_turn(session, session_id=SID, turn=turn, agents=agents, seed=11)
        manifest, records, _world = await export_session(session, SID, run_id="e2e", seed=11)
    await engine.dispose()

    path = tmp_path / "e2e.jsonl"
    with TraceWriter(path, manifest) as writer:
        for record in records:
            writer.append(record)

    report = validate_trace(path)
    assert report.ok, report.errors
    assert report.n_turns == len(records)

    manifest, records = read_trace(path)
    assert manifest.state_fidelity == "full"

    judge = build_judge(provider="stub")
    verdicts = []
    for record in records:
        raw = await judge.judge(
            JudgeContext(
                session_id=SID,
                turn=record.turn,
                agent_id=record.agent_id,
                monologue=record.monologue,
                public_message=record.public_message,
                action=record.action,
                arguments=record.arguments,
                outcome=record.outcome,
                balance=record.state.balance,
                trust_score=record.state.trust_score,
                target_id=record.arguments.get("target"),
                transactions=[],
            )
        )
        verdict = normalize_verdict(raw, actor_id=record.agent_id)
        verdicts.append(
            {
                "turn": record.turn,
                "agent_id": record.agent_id,
                "is_deceptive": verdict.is_deceptive,
                "deception_type": verdict.deception_type,
                "target_id": verdict.target_id,
                "confidence": verdict.confidence,
                "sophistication": verdict.sophistication,
            }
        )

    assert len(verdicts) == len(records)
    for v in verdicts:
        assert (v["sophistication"] is None) is (not v["is_deceptive"])

    metrics = coherence_metrics(verdicts, lifespans=manifest.lifespans())
    assert "per_model" in metrics

    alive_at = {r.turn: (r.state.alive or []) for r in records}
    null = permutation_null(verdicts, alive_at=alive_at, n_iter=50)
    corrected = bh_correct(null)
    assert corrected["n_tests"] >= 0
    assert corrected["n_significant"] <= corrected["n_tests"]


async def test_pipeline_survives_a_run_with_no_deception(tmp_path):
    """Coherence over an empty deceptive set must return, not raise.

    A condition arm can legitimately produce zero labelled lies; if the metric
    blows up there, the sweep dies on its most interesting cell.
    """
    verdicts = [
        {"turn": t, "agent_id": "a0", "is_deceptive": False,
         "deception_type": "none", "target_id": None, "confidence": 0.9,
         "sophistication": None}
        for t in range(1, 6)
    ]
    metrics = coherence_metrics(verdicts, lifespans={"a0": 5})
    assert metrics["per_model"] == {}

    null = permutation_null(verdicts, alive_at={t: ["a0"] for t in range(1, 6)}, n_iter=10)
    assert bh_correct(null)["n_tests"] == 0


async def test_the_exported_trace_says_where_each_agent_stood(tmp_path):
    """A restored turn has to reproduce the prompt, and the prompt names a venue."""
    from app.oracle.world_data import BUILT_VENUES

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, "venue-e2e", _roster(), seed=5)
        agents = build_agents(roster=_roster())
        for turn in range(1, 5):
            await run_turn(session, session_id="venue-e2e", turn=turn, agents=agents, seed=5)
        _manifest, records, _world = await export_session(
            session, "venue-e2e", run_id="venue-e2e", seed=5
        )
    await engine.dispose()

    from app.oracle.world_data import ACTION_VENUE

    turns = [r for r in records if r.kind == "turn"]
    assert turns
    for record in turns:
        assert record.state.venue in BUILT_VENUES, record.state.venue
        if record.action not in ACTION_VENUE:
            continue
        assert record.state.venue == ACTION_VENUE[record.action]


def test_env_version_is_current():
    from app.config import ENV_VERSION

    assert ENV_VERSION == "darwin-3.0"
