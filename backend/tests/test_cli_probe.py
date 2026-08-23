import json

from app.cli.main import main
from app.trace.io import TraceWriter
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    RunManifest,
    TurnRecord,
    TurnState,
)


def _trace(path):
    manifest = RunManifest(
        kind="run", schema_version=4, run_id="cli", env=EnvManifest(name="darwin", seed=2),
        horizon=20,
        agents=[AgentManifest(agent_id="a0", turns_alive=20, specialty="food"),
                AgentManifest(agent_id="a1", turns_alive=20, specialty="ore"),
                AgentManifest(agent_id="a2", turns_alive=20, specialty="tech")],
    )
    with TraceWriter(path, manifest) as w:
        for turn in range(1, 13):
            for agent, bal in (("a0", 4.0), ("a1", 9.0), ("a2", 0.8)):
                w.append(TurnRecord(
                    kind="turn", turn=turn, agent_id=agent, action="work",
                    monologue="m", public_message="p",
                    state=TurnState(balance=bal, trust_score=50.0,
                                    inventory={"ore": 1, "food": 1, "tech": 1},
                                    alive=["a0", "a1", "a2"]),
                ))
    return path


def _verdicts(path):
    rows = [{"turn": 3, "agent_id": "a0", "is_deceptive": True,
             "deception_type": "misdirection", "target_id": "a1", "confidence": 0.9}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_probe_mine_run_score_end_to_end(tmp_path, capsys):
    trace = _trace(tmp_path / "t.jsonl")
    verdicts = _verdicts(tmp_path / "v.jsonl")
    probes = tmp_path / "probes.jsonl"
    results = tmp_path / "results.jsonl"

    assert main(["probe", "mine", str(trace), "--verdicts", str(verdicts),
                 "--out", str(probes), "--k-turns", "3"]) == 0
    assert "mined 2 probes" in capsys.readouterr().out

    assert main(["probe", "run", str(probes), "--model", "stub/model",
                 "--provider", "stub", "--judge-provider", "stub",
                 "--samples", "2", "--out", str(results)]) == 0
    assert "wrote 4 runs" in capsys.readouterr().out

    assert main(["probe", "score", str(results)]) == 0
    printed = capsys.readouterr().out
    assert "propensity" in printed
    assert "susceptibility" in printed
    assert "pressure threshold" in printed


def test_probe_run_defaults_to_the_public_split(tmp_path, capsys):
    trace = _trace(tmp_path / "t.jsonl")
    verdicts = _verdicts(tmp_path / "v.jsonl")
    probes = tmp_path / "probes.jsonl"
    assert main(["probe", "mine", str(trace), "--verdicts", str(verdicts),
                 "--out", str(probes)]) == 0
    capsys.readouterr()

    rows = [json.loads(x) for x in probes.read_text(encoding="utf-8").splitlines() if x.strip()]
    for row in rows:
        row["split"] = "heldout"
    probes.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    assert main(["probe", "run", str(probes), "--model", "stub/model",
                 "--provider", "stub", "--judge-provider", "stub",
                 "--samples", "1", "--out", str(tmp_path / "r.jsonl")]) == 1
    assert "no probes in split 'public'" in capsys.readouterr().out


def test_mine_warns_when_the_trace_has_no_state(tmp_path, capsys):
    path = tmp_path / "bare.jsonl"
    manifest = RunManifest(
        kind="run", schema_version=4, run_id="bare", env=EnvManifest(name="darwin"),
        horizon=10, state_fidelity="partial",
        agents=[AgentManifest(agent_id="a0", turns_alive=10),
                AgentManifest(agent_id="a1", turns_alive=10)],
    )
    with TraceWriter(path, manifest) as w:
        for turn in range(1, 6):
            for agent in ("a0", "a1"):
                w.append(TurnRecord(kind="turn", turn=turn, agent_id=agent,
                                    action="work", monologue="m", public_message="p"))
    verdicts = tmp_path / "v.jsonl"
    verdicts.write_text(json.dumps(
        {"turn": 2, "agent_id": "a0", "is_deceptive": True,
         "deception_type": "misdirection", "target_id": "a1", "confidence": 0.9}
    ) + "\n", encoding="utf-8")

    assert main(["probe", "mine", str(path), "--verdicts", str(verdicts),
                 "--out", str(tmp_path / "p.jsonl")]) == 0
    printed = capsys.readouterr().out
    assert "no per-turn state" in printed
    assert "'None': 2" in printed
