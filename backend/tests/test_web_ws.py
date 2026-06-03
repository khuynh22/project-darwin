"""End-to-end WebSocket room test: live events fan out only to their own
session's room. This is the actual 'multiple users watching at once' path."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

AGENTS = [
    {"agent_id": c, "display_name": c, "provider": "stub", "sprite": c}
    for c in ("red", "blue", "green")
]


def test_ws_room_is_session_scoped():
    with TestClient(app) as client:
        a = client.post("/sessions").json()["session_id"]
        b = client.post("/sessions").json()["session_id"]
        assert client.post(f"/sessions/{a}/configure", json={"agents": AGENTS}).status_code == 200
        assert client.post(f"/sessions/{b}/configure", json={"agents": AGENTS}).status_code == 200

        # A viewer subscribed to session A's room...
        with client.websocket_connect(f"/ws/{a}") as ws_a:
            first = ws_a.receive_json()
            assert first["event"] == "snapshot"
            assert first["snapshot"]["session_id"] == a

            # Driving A's turn pushes a 'turn' event into A's room only.
            client.post(f"/sessions/{a}/run?turns=1")
            evt = ws_a.receive_json()
            assert evt["event"] == "turn"
            assert evt["snapshot"]["session_id"] == a
            assert evt["snapshot"]["turn"] == 1

        # A viewer on session B sees B's state (turn 0 — B never ran), not A's.
        with client.websocket_connect(f"/ws/{b}") as ws_b:
            firstb = ws_b.receive_json()
            assert firstb["snapshot"]["session_id"] == b
            assert firstb["snapshot"]["turn"] == 0


def test_configure_requires_openrouter_key():
    """Real (openrouter) agents must come with a key — no silent stub fallback."""
    real = [
        {
            "agent_id": c,
            "display_name": c,
            "provider": "openrouter",
            "model": "openai/gpt-5",
            "sprite": c,
        }
        for c in ("red", "blue", "green")
    ]
    with TestClient(app) as client:
        s = client.post("/sessions").json()["session_id"]

        # No key -> rejected
        r = client.post(f"/sessions/{s}/configure", json={"agents": real})
        assert "error" in r.json() and "openrouter" in r.json()["error"].lower()

        # With a key -> accepted (no network: configure doesn't run a turn)
        r2 = client.post(
            f"/sessions/{s}/configure",
            json={"agents": real, "keys": {"openrouter": "sk-or-test"}},
        )
        assert r2.json().get("agent_count") == 3, r2.text
