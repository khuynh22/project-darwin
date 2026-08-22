import json

import pytest

from app.cli.main import main
from app.trace.io import TraceWriter
from app.trace.schema import AgentManifest, EnvManifest, RunManifest, TurnRecord


def _trace(path):
    manifest = RunManifest(
        kind="run", schema_version=4, run_id="demo",
        env=EnvManifest(name="darwin", seed=1), horizon=2,
        agents=[AgentManifest(agent_id="opus", turns_alive=2)],
    )
    with TraceWriter(path, manifest) as w:
        w.append(TurnRecord(kind="turn", turn=1, agent_id="opus", action="work",
                            public_message="hi"))
    return path


def test_validate_returns_zero_for_good_trace(tmp_path, capsys):
    path = _trace(tmp_path / "t.jsonl")
    assert main(["validate", str(path)]) == 0
    assert "ok" in capsys.readouterr().out.lower()


def test_validate_returns_one_for_bad_trace(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps({"kind": "turn", "turn": 1, "agent_id": "a", "action": "work"}) + "\n",
        encoding="utf-8",
    )
    assert main(["validate", str(path)]) == 1
    assert "manifest" in capsys.readouterr().out.lower()


def test_upgrade_writes_a_valid_v4_trace(tmp_path):
    src = tmp_path / "legacy.jsonl"
    src.write_text(
        json.dumps({"schema_version": 2, "turn": 1, "agent_id": "opus", "monologue": "m",
                    "action": "work", "arguments": {}, "outcome": "ok"}) + "\n",
        encoding="utf-8",
    )
    models = tmp_path / "models.json"
    models.write_text(json.dumps({"opus": "anthropic/claude-opus-4.7"}), encoding="utf-8")
    out = tmp_path / "v4.jsonl"

    assert main(["upgrade", str(src), "--out", str(out), "--run-id", "r1",
                 "--models", str(models)]) == 0
    assert main(["validate", str(out)]) == 0


def test_replay_prints_the_triple(tmp_path, capsys):
    path = _trace(tmp_path / "t.jsonl")
    assert main(["replay", str(path)]) == 0
    out = capsys.readouterr().out
    assert "opus" in out and "work" in out and "hi" in out


def test_replay_filters_by_agent(tmp_path, capsys):
    path = tmp_path / "t.jsonl"
    manifest = RunManifest(
        kind="run", schema_version=4, run_id="demo",
        env=EnvManifest(name="darwin"), horizon=2,
        agents=[AgentManifest(agent_id="opus", turns_alive=2),
                AgentManifest(agent_id="grok", turns_alive=2)],
    )
    with TraceWriter(path, manifest) as w:
        w.append(TurnRecord(kind="turn", turn=1, agent_id="opus", action="work"))
        w.append(TurnRecord(kind="turn", turn=1, agent_id="grok", action="steal"))

    assert main(["replay", str(path), "--agent", "grok"]) == 0
    out = capsys.readouterr().out
    assert "steal" in out
    assert "\nt   1 opus" not in out


def test_bare_invocation_prints_help(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_unknown_command_exits_two(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["nope"])
    assert exc.value.code == 2
