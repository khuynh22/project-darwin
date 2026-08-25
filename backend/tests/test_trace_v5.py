"""v5 adds complete restorable state and per-turn world records."""

import pytest
from pydantic import ValidationError

from app.trace.io import TraceWriter, read_trace, read_world
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    RunManifest,
    TurnRecord,
    TurnState,
    WorldRecord,
    parse_record,
)
from app.trace.validate import validate_trace


def _manifest(version=5, horizon=10):
    return RunManifest(
        kind="run", schema_version=version, run_id="v5",
        env=EnvManifest(name="darwin", seed=1), horizon=horizon,
        agents=[AgentManifest(agent_id="a0", turns_alive=horizon)],
    )


def test_turn_state_carries_the_fields_v4_omitted():
    state = TurnState(balance=4.0, steal_count=5, allies=["a1"], share_balance=False)
    assert state.steal_count == 5
    assert state.allies == ["a1"]
    assert state.share_balance is False


def test_reserved_fields_default_to_none():
    """office/tier/capacity are schema-reserved until their layer ships."""
    state = TurnState()
    assert state.office is None
    assert state.tier is None
    assert state.capacity is None


def test_deferred_entries_round_trip():
    state = TurnState(deferred=[{"kind": "investment", "amount": 9.0, "maturity_turn": 24}])
    assert state.deferred[0].maturity_turn == 24


def test_world_record_parses():
    record = parse_record({
        "kind": "world", "turn": 3,
        "offices": {"auditor": "a0", "bank": None},
        "prices": {"ore": 0.3},
    })
    assert isinstance(record, WorldRecord)
    assert record.offices["auditor"] == "a0"
    assert record.contracts == []


def test_unknown_kind_still_rejected():
    with pytest.raises(ValidationError):
        parse_record({"kind": "nonsense", "turn": 1})


def test_world_records_do_not_pollute_the_turn_stream(tmp_path):
    """Every existing reader must keep working against a v5 file."""
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(WorldRecord(kind="world", turn=1))
        w.append(TurnRecord(kind="turn", turn=1, agent_id="a0", action="work"))
        w.append(WorldRecord(kind="world", turn=2))
        w.append(TurnRecord(kind="turn", turn=2, agent_id="a0", action="work"))

    manifest, turns = read_trace(path)
    assert [t.turn for t in turns] == [1, 2]
    assert all(isinstance(t, TurnRecord) for t in turns)

    world = read_world(path)
    assert sorted(world) == [1, 2]


def test_world_only_trace_reads_as_empty_world_for_v4(tmp_path):
    path = tmp_path / "v4.jsonl"
    with TraceWriter(path, _manifest(version=4)) as w:
        w.append(TurnRecord(kind="turn", turn=1, agent_id="a0", action="work"))
    assert read_world(path) == {}


def test_validate_accepts_world_records(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(WorldRecord(kind="world", turn=1))
        w.append(TurnRecord(kind="turn", turn=1, agent_id="a0", action="work"))
    report = validate_trace(path)
    assert report.ok, report.errors
    assert report.n_turns == 1  # world records are not turns


def test_validate_rejects_a_world_record_past_the_horizon(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest(horizon=5)) as w:
        w.append(WorldRecord(kind="world", turn=99))
    report = validate_trace(path)
    assert report.ok is False
    assert any("world turn 99" in e for e in report.errors)
