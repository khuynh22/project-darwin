from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import delete as sa_delete
from sqlalchemy import desc, select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models.agent import Agent
from app.models.api_key import ApiKeyStore, store_session_key
from app.models.deferred import DeferredAction
from app.models.ledger import ThoughtLog, Transaction, WorldEvent
from app.models.session import SimSession
from app.oracle.engine import run_turn, seed_roster
from app.runtime import SessionRuntime, registry
from app.ws import broadcaster

log = logging.getLogger("darwin")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Sessions load lazily (app.runtime); startup just ensures the schema exists.
    await init_db()
    yield


app = FastAPI(title="Project Darwin Oracle", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BALANCE_VISIBILITY_DEFAULT = "fuzzy"
_VALID_VISIBILITY = {"public", "fuzzy", "hidden"}


# --- Provider metadata (global) ------------------------------------------------

# Only OpenRouter is offered; users pick any model id (e.g. "openai/gpt-5").
PROVIDER_DEFAULTS = [
    {"name": "openrouter", "default_model": "anthropic/claude-opus-4.7", "requires_key": True},
]
_KEY_REQUIRED = {p["name"] for p in PROVIDER_DEFAULTS if p["requires_key"]}

COLOR_OPTIONS = [
    "red", "blue", "green", "purple", "orange",
    "cyan", "pink", "yellow", "teal", "indigo",
]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/providers")
async def providers() -> dict:
    return {"providers": PROVIDER_DEFAULTS, "colors": COLOR_OPTIONS}


# --- Helpers -------------------------------------------------------------------


def _new_session_id() -> str:
    """Short, URL-safe, unguessable slug."""
    return secrets.token_urlsafe(8)


async def _purge_session(session, session_id: str) -> None:
    """Delete every row belonging to a session (scoped — never touches others)."""
    for model in (Transaction, ThoughtLog, WorldEvent, DeferredAction, Agent):
        await session.execute(
            sa_delete(model).where(model.session_id == session_id)
        )
    await session.execute(
        sa_delete(ApiKeyStore).where(ApiKeyStore.session_id == session_id)
    )


async def _state(session_id: str) -> dict:
    """Full snapshot for one session (includes invested capital for moderator)."""
    async with SessionLocal() as session:
        sim = await session.get(SimSession, session_id)
        agents = (
            (
                await session.execute(
                    select(Agent).where(Agent.session_id == session_id)
                )
            )
            .scalars()
            .all()
        )
        recent = (
            (
                await session.execute(
                    select(ThoughtLog)
                    .where(ThoughtLog.session_id == session_id)
                    .order_by(desc(ThoughtLog.id))
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        invested_map: dict[str, float] = {}
        deferred = (
            (
                await session.execute(
                    select(DeferredAction).where(
                        DeferredAction.session_id == session_id,
                        DeferredAction.resolved.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        for d in deferred:
            invested_map[d.actor_id] = round(
                invested_map.get(d.actor_id, 0) + d.amount, 2
            )
    return {
        "session_id": session_id,
        "turn": sim.current_turn if sim else 0,
        "balance_visibility": sim.balance_visibility if sim else BALANCE_VISIBILITY_DEFAULT,
        "agents": [
            {
                "agent_id": a.agent_id,
                "display_name": a.display_name,
                "provider": a.provider,
                "model": a.model,
                "balance": a.balance,
                "alive": a.alive,
                "spouse": a.spouse_id,
                "allies": list(a.allies or []),
                "enemies": list(a.enemies or []),
                "sprite": a.sprite,
                "consecutive_errors": a.consecutive_errors,
                "last_error": a.last_error,
                "trust_score": a.trust_score,
                "steal_count": a.steal_count,
                "inventory": a.inventory or {},
                "specialty": a.specialty,
                "invested": invested_map.get(a.agent_id, 0),
                "rest_bonus": a.rest_bonus,
                "will_target": a.will_target,
            }
            for a in agents
        ],
        "recent_thoughts": [
            {
                "turn": t.turn,
                "agent_id": t.agent_id,
                "monologue": t.monologue,
                "public_message": t.public_message or "",
                "action": t.action,
                "arguments": t.arguments,
                "outcome": t.outcome,
            }
            for t in recent
        ],
    }


def _not_found(session_id: str) -> JSONResponse:
    return JSONResponse({"error": f"session {session_id!r} not found"}, status_code=404)


# --- Session lifecycle ---------------------------------------------------------


@app.post("/sessions")
async def create_session() -> dict:
    """Create a fresh, empty session. The creator then POSTs /configure."""
    session_id = _new_session_id()
    async with SessionLocal() as session:
        session.add(
            SimSession(
                session_id=session_id,
                current_turn=0,
                balance_visibility=BALANCE_VISIBILITY_DEFAULT,
                status="configuring",
            )
        )
        await session.commit()
    return {"session_id": session_id}


@app.post("/sessions/{session_id}/configure")
async def configure_simulation(session_id: str, body: dict):
    """Set up a roster (resets only this session). Upserts the session row so a
    bookmarked ``/session/{id}`` link works without a prior ``POST /sessions``."""
    settings = get_settings()

    agents_list = body.get("agents", [])
    if not (settings.min_agents <= len(agents_list) <= settings.max_agents):
        return {
            "error": f"Need {settings.min_agents}-{settings.max_agents} agents, got {len(agents_list)}"
        }

    visibility = body.get("balance_visibility", BALANCE_VISIBILITY_DEFAULT)
    if visibility not in _VALID_VISIBILITY:
        return {
            "error": f"balance_visibility must be one of {sorted(_VALID_VISIBILITY)}, got {visibility!r}"
        }

    # Per-session BYOK: { provider: raw_key }
    keys: dict[str, str] = {
        p: k for p, k in (body.get("keys") or {}).items() if k
    }

    # Build roster specs
    roster: list[dict] = []
    for a in agents_list:
        agent_id = (a.get("agent_id", "") or "").lower().replace(" ", "_")
        if not agent_id:
            return {"error": "Each agent needs an agent_id"}
        personality = (a.get("personality") or "").strip()
        if not personality:
            _auto = [
                "Adaptive strategist who reads the room and adjusts tactics each turn.",
                "Cautious optimizer who minimizes risk and builds steady wealth.",
                "Bold opportunist who takes big swings and exploits market gaps.",
                "Social connector who builds alliances and leverages relationships.",
                "Calculating survivalist who hoards resources and strikes when advantageous.",
            ]
            personality = _auto[len(roster) % len(_auto)]
        provider = a.get("provider", "stub")
        spec = {
            "agent_id": agent_id,
            "display_name": a.get("display_name", agent_id.upper()),
            "provider": provider,
            "model": a.get("model", ""),
            "personality": personality,
            "sprite": a.get("sprite", "blue"),
        }
        if keys.get(provider):
            spec["api_key"] = keys[provider]
        roster.append(spec)

    ids = [r["agent_id"] for r in roster]
    if len(set(ids)) != len(ids):
        return {"error": "Duplicate agent_id found"}

    # Every key-requiring provider in use must have a key (no silent stub fallback).
    missing = sorted(
        {r["provider"] for r in roster if r["provider"] in _KEY_REQUIRED and not keys.get(r["provider"])}
    )
    if missing:
        return {"error": f"Missing API key for: {', '.join(missing)}"}

    # Reset ONLY this session, store keys, seed roster
    async with SessionLocal() as session:
        await _purge_session(session, session_id)
        for provider, raw in keys.items():
            await store_session_key(session, session_id, provider, raw)
        await session.commit()

    async with SessionLocal() as session:
        await seed_roster(session, session_id, roster=roster)
        sim = await session.get(SimSession, session_id)
        if sim is None:  # upsert: link was navigated to before /sessions created a row
            sim = SimSession(session_id=session_id)
            session.add(sim)
        sim.current_turn = 0
        sim.balance_visibility = visibility
        sim.status = "ready"
        await session.commit()

    # Register live runtime (roster carries decrypted keys, in-memory only)
    registry.put(
        SessionRuntime(
            session_id=session_id,
            balance_visibility=visibility,
            roster=roster,
        )
    )

    snapshot = await _state(session_id)
    await broadcaster.broadcast(session_id, {"event": "snapshot", "snapshot": snapshot})
    return {"session_id": session_id, "agent_count": len(roster), "agents": ids}


@app.get("/sessions/{session_id}/state")
async def get_state(session_id: str):
    async with SessionLocal() as session:
        if await session.get(SimSession, session_id) is None:
            return _not_found(session_id)
    return await _state(session_id)


@app.get("/sessions/{session_id}/ledger")
async def ledger(session_id: str, limit: int = 100) -> dict:
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(Transaction)
                    .where(Transaction.session_id == session_id)
                    .order_by(desc(Transaction.id))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return {
        "transactions": [
            {
                "turn": r.turn,
                "actor": r.actor_id,
                "target": r.target_id,
                "action": r.action,
                "delta": r.delta,
                "note": r.note,
                "payload": r.payload,
            }
            for r in rows
        ]
    }


@app.get("/sessions/{session_id}/events")
async def events(session_id: str, limit: int = 50) -> dict:
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(WorldEvent)
                    .where(WorldEvent.session_id == session_id)
                    .order_by(desc(WorldEvent.id))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return {
        "events": [{"turn": e.turn, "kind": e.kind, "payload": e.payload} for e in rows]
    }


# --- Turn driving --------------------------------------------------------------


async def _drive_turns(session_id: str, count: int):
    """Run up to ``count`` turns for a session under its per-session lock."""
    from app.agents.factory import build_agents

    runtime = await registry.get_or_load(session_id)
    if runtime is None:
        return _not_found(session_id)

    settings = get_settings()
    cap = max(0, min(count, settings.max_turns))
    agents = build_agents(roster=runtime.roster)
    apex = None
    eliminated: list[str] = []

    async with runtime.lock:
        # Reflect the real current turn even if cap == 0 (no-op call).
        async with SessionLocal() as session:
            sim0 = await session.get(SimSession, session_id)
            turn = sim0.current_turn if sim0 else 0
        for _ in range(cap):
            async with SessionLocal() as session:
                sim = await session.get(SimSession, session_id)
                if sim is None:
                    return _not_found(session_id)
                sim.current_turn += 1
                turn = sim.current_turn
                result = await run_turn(
                    session,
                    session_id=session_id,
                    turn=turn,
                    agents=agents,
                    balance_visibility=runtime.balance_visibility,
                )
            snapshot = await _state(session_id)
            if result.paused:
                await broadcaster.broadcast(
                    session_id,
                    {
                        "event": "simulation_paused",
                        "turn": turn,
                        "agent_id": result.pause_agent_id,
                        "reason": result.pause_reason,
                        "snapshot": snapshot,
                    },
                )
                return {
                    "session_id": session_id,
                    "final_turn": turn,
                    "apex": None,
                    "eliminated": eliminated,
                    "paused": True,
                    "agent_id": result.pause_agent_id,
                    "reason": result.pause_reason,
                }
            await broadcaster.broadcast(
                session_id, {"event": "turn", "turn": turn, "snapshot": snapshot}
            )
            eliminated.extend(result.eliminated)
            if result.apex_declared:
                apex = result.apex_declared
                break

    return {
        "session_id": session_id,
        "final_turn": turn,
        "apex": apex,
        "eliminated": eliminated,
    }


@app.post("/sessions/{session_id}/turn")
async def step_turn(session_id: str):
    """Drive a single turn (manual stepping/debug)."""
    return await _drive_turns(session_id, 1)


@app.post("/sessions/{session_id}/run")
async def run_many(session_id: str, turns: int = 10):
    """Run N turns; returns when finished, apex declared, or paused on error."""
    return await _drive_turns(session_id, turns)


@app.post("/sessions/{session_id}/reset")
async def reset_simulation(session_id: str):
    """Wipe a single session's data (keeps the session id so links survive)."""
    async with SessionLocal() as session:
        sim = await session.get(SimSession, session_id)
        if sim is None:
            return _not_found(session_id)
        await _purge_session(session, session_id)
        sim.current_turn = 0
        sim.balance_visibility = BALANCE_VISIBILITY_DEFAULT
        sim.status = "configuring"
        await session.commit()
    registry.forget(session_id)
    snapshot = await _state(session_id)
    await broadcaster.broadcast(session_id, {"event": "snapshot", "snapshot": snapshot})
    return {"reset": True, "session_id": session_id}


@app.get("/sessions/{session_id}/export/thoughts")
async def export_thoughts(session_id: str):
    """Download a session's thought log as JSONL (queried live from the DB)."""
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(ThoughtLog)
                    .where(ThoughtLog.session_id == session_id)
                    .order_by(ThoughtLog.id)
                )
            )
            .scalars()
            .all()
        )
    import json

    lines = [
        json.dumps(
            {
                "schema_version": 2,
                "turn": t.turn,
                "agent_id": t.agent_id,
                "monologue": t.monologue,
                "public_message": t.public_message or "",
                "action": t.action,
                "arguments": t.arguments,
                "outcome": t.outcome,
            },
            default=str,
        )
        for t in rows
    ]
    body = "\n".join(lines) + ("\n" if lines else "")
    return Response(
        content=body,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="session_{session_id}.jsonl"'
        },
    )


@app.post("/sessions/{session_id}/agents/{agent_id}/remove")
async def remove_agent(session_id: str, agent_id: str):
    """Force-eliminate a failing agent so the simulation can continue."""
    async with SessionLocal() as session:
        sim = await session.get(SimSession, session_id)
        if sim is None:
            return _not_found(session_id)
        agent = await session.get(Agent, (session_id, agent_id))
        if agent is None:
            return {"error": "agent not found"}
        agent.alive = False
        agent.eliminated_at_turn = sim.current_turn
        agent.consecutive_errors = 0
        agent.last_error = None
        session.add(
            WorldEvent(
                session_id=session_id,
                turn=sim.current_turn,
                kind="provider_failure",
                payload={"agent_id": agent_id, "removed_by_user": True},
            )
        )
        await session.commit()
        turn = sim.current_turn
    snapshot = await _state(session_id)
    await broadcaster.broadcast(
        session_id, {"event": "turn", "turn": turn, "snapshot": snapshot}
    )
    return {"removed": agent_id, "turn": turn}


@app.post("/sessions/{session_id}/simulation/resume")
async def resume_simulation(session_id: str):
    """Clear error counters for all alive agents so the simulation can resume."""
    async with SessionLocal() as session:
        sim = await session.get(SimSession, session_id)
        if sim is None:
            return _not_found(session_id)
        agents = (
            (
                await session.execute(
                    select(Agent).where(
                        Agent.session_id == session_id, Agent.alive.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        for a in agents:
            a.consecutive_errors = 0
            a.last_error = None
        await session.commit()
        turn = sim.current_turn
    return {"resumed": True, "turn": turn}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str) -> None:
    await broadcaster.connect(session_id, ws)
    try:
        snapshot = await _state(session_id)
        await ws.send_json({"event": "snapshot", "snapshot": snapshot})
        while True:
            # keep connection alive; ignore client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(session_id, ws)
