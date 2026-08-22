import json

from app.cli.main import main


def _roster_file(tmp_path):
    roster = [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(roster), encoding="utf-8")
    return path


def _spec_file(tmp_path, roster_path, out_dir, **over):
    spec = {
        "experiment": "clis", "roster": str(roster_path),
        "conditions": ["neutral"], "seeds": [1, 2], "turns": 3,
        "out": str(out_dir), "concurrency": 1,
    }
    spec.update(over)
    path = tmp_path / "exp.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_dry_run_lists_cells_without_running(tmp_path, capsys):
    out = tmp_path / "runs"
    spec = _spec_file(tmp_path, _roster_file(tmp_path), out)
    assert main(["sweep", str(spec), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "clis:neutral:1" in printed
    assert "clis:neutral:2" in printed
    assert not out.exists()


def test_sweep_runs_and_traces_validate(tmp_path):
    out = tmp_path / "runs"
    spec = _spec_file(tmp_path, _roster_file(tmp_path), out)
    assert main(["sweep", str(spec), "--out", str(out)]) == 0
    traces = sorted(out.glob("*.jsonl"))
    assert len(traces) == 2
    for trace in traces:
        assert main(["validate", str(trace)]) == 0


def test_second_sweep_resumes(tmp_path, capsys):
    out = tmp_path / "runs"
    spec = _spec_file(tmp_path, _roster_file(tmp_path), out)
    assert main(["sweep", str(spec), "--out", str(out)]) == 0
    capsys.readouterr()
    assert main(["sweep", str(spec), "--out", str(out)]) == 0
    assert "2 skipped" in capsys.readouterr().out
