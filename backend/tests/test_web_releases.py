"""The gallery endpoints are read-only: a viewer must not be able to mutate state."""

import json

import pytest
from fastapi.testclient import TestClient

from app.trace.io import TraceWriter
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    RunManifest,
    TurnRecord,
    TurnState,
)


def _seed_release(root, run_id="rel1", n_turns=8, scores=False):
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    manifest = RunManifest(
        kind="run", schema_version=4, run_id=run_id,
        env=EnvManifest(name="darwin", seed=1), horizon=n_turns, condition="neutral",
        agents=[AgentManifest(agent_id="a0", turns_alive=n_turns, model="m/one"),
                AgentManifest(agent_id="a1", turns_alive=n_turns, model="m/two")],
    )
    with TraceWriter(d / "trace.jsonl", manifest) as w:
        for turn in range(1, n_turns + 1):
            for agent in ("a0", "a1"):
                w.append(TurnRecord(
                    kind="turn", turn=turn, agent_id=agent, action="work",
                    monologue="m", public_message="p", outcome="ok",
                    state=TurnState(balance=5.0, trust_score=50.0)))
    (d / "verdicts.jsonl").write_text(json.dumps(
        {"turn": 3, "agent_id": "a0", "is_deceptive": True,
         "deception_type": "misdirection", "target_id": "a1",
         "confidence": 0.9, "sophistication": 3}) + "\n", encoding="utf-8")
    if scores:
        (d / "scores.json").write_text(json.dumps([{"model": "m/one", "excluded": 0}]),
                                       encoding="utf-8")
    return d


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "_releases_root", lambda: tmp_path)
    return TestClient(main_mod.app)


def test_index_lists_seeded_release(client, tmp_path):
    _seed_release(tmp_path)
    body = client.get("/releases").json()
    assert [r["run_id"] for r in body["releases"]] == ["rel1"]
    assert body["releases"][0]["n_turns"] == 16
    assert "m/one" in body["releases"][0]["models"]


def test_index_is_empty_without_releases(client):
    assert client.get("/releases").json() == {"releases": []}


def test_detail_includes_agents(client, tmp_path):
    _seed_release(tmp_path)
    body = client.get("/releases/rel1").json()
    assert body["horizon"] == 8
    assert {a["agent_id"] for a in body["agents"]} == {"a0", "a1"}


def test_unknown_release_is_404(client):
    assert client.get("/releases/nope").status_code == 404
    assert client.get("/releases/nope/turns").status_code == 404
    assert client.get("/releases/nope/verdicts").status_code == 404


def test_turns_paginate(client, tmp_path):
    _seed_release(tmp_path, n_turns=10)
    body = client.get("/releases/rel1/turns?offset=0&limit=6").json()
    assert body["total"] == 20
    assert len(body["turns"]) == 6
    assert body["offset"] == 0

    second = client.get("/releases/rel1/turns?offset=6&limit=6").json()
    assert second["turns"] != body["turns"]


def test_limit_is_clamped(client, tmp_path):
    """Returning a 2000-turn trace in one response is a defect, not a convenience."""
    _seed_release(tmp_path, n_turns=10)
    body = client.get("/releases/rel1/turns?limit=10000").json()
    assert body["limit"] == 200
    assert len(body["turns"]) <= 200


def test_verdicts_filter(client, tmp_path):
    _seed_release(tmp_path)
    assert len(client.get("/releases/rel1/verdicts").json()["verdicts"]) == 1
    assert client.get("/releases/rel1/verdicts?turn=3").json()["verdicts"]
    assert client.get("/releases/rel1/verdicts?turn=99").json()["verdicts"] == []
    assert client.get("/releases/rel1/verdicts?agent=a1").json()["verdicts"] == []


def test_scores_404_when_not_published(client, tmp_path):
    _seed_release(tmp_path)
    assert client.get("/releases/rel1/scores").status_code == 404


def test_scores_served_when_present(client, tmp_path):
    _seed_release(tmp_path, scores=True)
    body = client.get("/releases/rel1/scores").json()
    assert body["scores"][0]["model"] == "m/one"


def test_gallery_requests_do_not_create_sessions(client, tmp_path):
    """A read-only endpoint must not be a way to spawn simulation state."""
    _seed_release(tmp_path)
    client.get("/releases")
    client.get("/releases/rel1")
    client.get("/releases/rel1/turns")
    client.get("/releases/rel1/verdicts")
    # Nothing above should have registered a live session.
    from app.runtime import SessionRegistry

    assert not getattr(SessionRegistry, "_sessions", {})
