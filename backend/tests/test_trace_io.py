import json

from app.trace.io import TraceWriter, iter_turns, read_trace
from app.trace.schema import AgentManifest, EnvManifest, RunManifest, TurnRecord
from app.trace.validate import validate_trace


def _manifest() -> RunManifest:
    return RunManifest(
        kind="run",
        schema_version=4,
        run_id="demo",
        env=EnvManifest(name="darwin", version="abc", seed=7),
        horizon=2,
        agents=[AgentManifest(agent_id="opus", turns_alive=2)],
    )


def _turn(n: int) -> TurnRecord:
    return TurnRecord(kind="turn", turn=n, agent_id="opus", action="work")


def test_round_trip(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(_turn(1))
        w.append(_turn(2))

    manifest, turns = read_trace(path)
    assert manifest.run_id == "demo"
    assert [t.turn for t in turns] == [1, 2]
    assert list(iter_turns(path)) == turns


def test_manifest_is_first_line(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(_turn(1))
    first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert first["kind"] == "run"
    assert first["schema_version"] == 4


def test_read_trace_rejects_a_file_with_no_manifest(tmp_path):
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps({"kind": "turn", "turn": 1, "agent_id": "opus", "action": "work"}) + "\n",
        encoding="utf-8",
    )
    try:
        read_trace(path)
    except ValueError as exc:
        assert "manifest" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_validate_accepts_good_trace(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(_turn(1))
    report = validate_trace(path)
    assert report.ok is True
    assert report.n_turns == 1
    assert report.errors == []


def test_validate_rejects_missing_manifest(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        json.dumps({"kind": "turn", "turn": 1, "agent_id": "a", "action": "work"}) + "\n",
        encoding="utf-8",
    )
    report = validate_trace(path)
    assert report.ok is False
    assert any("manifest" in e for e in report.errors)


def test_validate_rejects_turn_for_unknown_agent(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(TurnRecord(kind="turn", turn=1, agent_id="ghost", action="work"))
    report = validate_trace(path)
    assert report.ok is False
    assert any("ghost" in e for e in report.errors)


def test_validate_rejects_turn_past_horizon(tmp_path):
    path = tmp_path / "t.jsonl"
    with TraceWriter(path, _manifest()) as w:
        w.append(TurnRecord(kind="turn", turn=99, agent_id="opus", action="work"))
    report = validate_trace(path)
    assert report.ok is False
    assert any("horizon" in e for e in report.errors)


def test_writer_flushes_each_row(tmp_path):
    """A sweep killed mid-run must leave a truncated-but-parseable trace."""
    path = tmp_path / "t.jsonl"
    writer = TraceWriter(path, _manifest())
    writer.append(_turn(1))
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    writer.close()
