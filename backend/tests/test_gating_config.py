"""The gating flag is configured per session and reported in the snapshot."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as main_mod

ROSTER = [
    {"agent_id": c, "display_name": c.title(), "provider": "stub", "personality": "x", "sprite": c}
    for c in ("red", "blue", "green")
]


@pytest.fixture
def client():
    with TestClient(main_mod.app) as client:
        yield client


def test_gating_defaults_off(client):
    sid = client.post("/sessions").json()["session_id"]
    client.post(f"/sessions/{sid}/configure", json={"agents": ROSTER})

    state = client.get(f"/sessions/{sid}/state").json()

    assert state["venue_gating"] is False


def test_gating_can_be_turned_on_at_configure_time(client):
    sid = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{sid}/configure",
        json={"agents": ROSTER, "venue_gating": True},
    )

    state = client.get(f"/sessions/{sid}/state").json()

    assert state["venue_gating"] is True


def test_a_non_boolean_flag_is_rejected(client):
    sid = client.post("/sessions").json()["session_id"]
    resp = client.post(
        f"/sessions/{sid}/configure",
        json={"agents": ROSTER, "venue_gating": "yes please"},
    )

    # configure reports bad input as an `error` key on a 200, the same way
    # `condition` and `balance_visibility` already do -- not a status code.
    assert "venue_gating" in resp.json()["error"]
