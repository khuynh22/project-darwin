import json

from app.releases import (
    list_releases,
    load_release,
    read_turns,
    read_verdicts,
)
from app.trace.io import TraceWriter
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    RunManifest,
    TurnRecord,
    TurnState,
)


def _release(root, run_id="r1", n_turns=6, fidelity="full", verdicts=True, about=None):
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    manifest = RunManifest(
        kind="run", schema_version=4, run_id=run_id,
        env=EnvManifest(name="darwin", seed=1), horizon=n_turns, condition="neutral",
        state_fidelity=fidelity,
        agents=[AgentManifest(agent_id="a0", turns_alive=n_turns,
                              model="anthropic/claude-opus-4.7"),
                AgentManifest(agent_id="a1", turns_alive=n_turns, model="openai/gpt-5")],
    )
    with TraceWriter(d / "trace.jsonl", manifest) as w:
        for turn in range(1, n_turns + 1):
            for agent in ("a0", "a1"):
                w.append(TurnRecord(
                    kind="turn", turn=turn, agent_id=agent, action="work",
                    monologue="m", public_message="p", outcome="ok",
                    state=TurnState(balance=5.0, trust_score=50.0),
                ))
    if verdicts:
        rows = [{"turn": 2, "agent_id": "a0", "is_deceptive": True,
                 "deception_type": "misdirection", "target_id": "a1",
                 "confidence": 0.9, "sophistication": 3, "rationale": "x"}]
        (d / "verdicts.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    if about:
        (d / "about.md").write_text(about, encoding="utf-8")
    return d


def test_lists_a_well_formed_release(tmp_path):
    _release(tmp_path)
    releases = list_releases(tmp_path)
    assert len(releases) == 1
    r = releases[0]
    assert r.run_id == "r1"
    assert r.n_agents == 2
    assert r.n_turns == 12
    assert r.horizon == 6
    assert r.state_fidelity == "full"
    assert r.has_verdicts is True
    assert "anthropic/claude-opus-4.7" in r.models


def test_directory_without_a_trace_is_skipped(tmp_path):
    (tmp_path / "empty").mkdir()
    _release(tmp_path, run_id="good")
    assert [r.run_id for r in list_releases(tmp_path)] == ["good"]


def test_malformed_trace_is_skipped_not_raised(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "trace.jsonl").write_text("{not json\n", encoding="utf-8")
    _release(tmp_path, run_id="good")
    assert [r.run_id for r in list_releases(tmp_path)] == ["good"]


def test_trace_without_a_manifest_is_skipped(tmp_path):
    bad = tmp_path / "bare"
    bad.mkdir()
    (bad / "trace.jsonl").write_text(
        json.dumps({"kind": "turn", "turn": 1, "agent_id": "a", "action": "work"}) + "\n",
        encoding="utf-8")
    assert list_releases(tmp_path) == []


def test_about_is_surfaced(tmp_path):
    _release(tmp_path, about="# Notes\nthe 335-turn game")
    assert "335-turn game" in list_releases(tmp_path)[0].about


def test_missing_verdicts_is_not_a_failure(tmp_path):
    _release(tmp_path, verdicts=False)
    assert list_releases(tmp_path)[0].has_verdicts is False
    assert read_verdicts(tmp_path, "r1") == {}


def test_partial_fidelity_surfaces(tmp_path):
    _release(tmp_path, fidelity="partial")
    assert list_releases(tmp_path)[0].state_fidelity == "partial"


def test_load_release_returns_none_for_unknown(tmp_path):
    _release(tmp_path)
    assert load_release(tmp_path, "nope") is None


def test_read_turns_paginates_and_reports_total(tmp_path):
    _release(tmp_path, n_turns=10)  # 20 turn rows
    page, total = read_turns(tmp_path, "r1", offset=0, limit=5)
    assert total == 20
    assert len(page) == 5
    assert page[0].turn == 1

    page2, total2 = read_turns(tmp_path, "r1", offset=5, limit=5)
    assert total2 == 20
    assert [t.turn for t in page2] != [t.turn for t in page]


def test_offset_past_the_end_returns_empty(tmp_path):
    _release(tmp_path, n_turns=4)
    page, total = read_turns(tmp_path, "r1", offset=999, limit=10)
    assert page == []
    assert total == 8


def test_verdicts_index_by_turn_and_agent(tmp_path):
    _release(tmp_path)
    index = read_verdicts(tmp_path, "r1")
    assert (2, "a0") in index
    assert index[(2, "a0")]["deception_type"] == "misdirection"


def test_repeated_reads_do_not_reparse(tmp_path):
    """A gallery page load must not re-parse a 2000-line trace per request."""
    _release(tmp_path, n_turns=20)
    first = load_release(tmp_path, "r1")
    second = load_release(tmp_path, "r1")
    assert first is second


def test_republished_release_is_picked_up(tmp_path):
    """The cache keys on mtime, so a republish is visible without a restart."""
    _release(tmp_path, n_turns=4)
    assert load_release(tmp_path, "r1").summary.horizon == 4
    _release(tmp_path, n_turns=9)
    assert load_release(tmp_path, "r1").summary.horizon == 9
