from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import desc, select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models.agent import Agent
from app.models.api_key import ApiKeyStore
from app.models.ledger import ThoughtLog, Transaction, WorldEvent
from app.oracle.engine import run_turn, seed_roster
from app.ws import broadcaster

log = logging.getLogger("darwin")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    from app.thought_export import start_export, stop_export

    await init_db()

    # Restore session if agents already exist in the DB (e.g. after backend restart)
    global _current_turn, _active_roster
    async with SessionLocal() as session:
        existing = (await session.execute(select(Agent))).scalars().all()
        if existing:
            # Rebuild roster from DB + stored API keys
            from app.models.api_key import get_key

            roster: list[dict] = []
            for a in existing:
                spec: dict = {
                    "agent_id": a.agent_id,
                    "display_name": a.display_name,
                    "provider": a.provider,
                    "personality": a.personality,
                    "sprite": a.sprite,
                }
                # Find the latest stored key for this provider
                keys = (
                    (
                        await session.execute(
                            select(ApiKeyStore)
                            .where(ApiKeyStore.provider == a.provider)
                            .order_by(ApiKeyStore.id.desc())
                        )
                    )
                    .scalars()
                    .first()
                )
                if keys:
                    raw = await get_key(session, keys.id)
                    if raw:
                        spec["api_key"] = raw
                roster.append(spec)
            _active_roster = roster

            # Restore turn counter from the latest thought log
            latest = (
                await session.execute(
                    select(ThoughtLog.turn).order_by(ThoughtLog.id.desc()).limit(1)
                )
            ).scalar()
            _current_turn = latest or 0
            start_export()
            log.info("Restored session: %d agents, turn %d", len(roster), _current_turn)

    yield
    stop_export()


app = FastAPI(title="Project Darwin Oracle", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level lock so REST callers can't race the turn loop.
_turn_lock = asyncio.Lock()
_current_turn = 0
_active_roster: list[dict] | None = None  # set by /configure, None = use default


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# --- Provider / API key management ---

PROVIDER_DEFAULTS = [
    {"name": "anthropic", "default_model": "claude-opus-4-7", "requires_key": True},
    {"name": "openai", "default_model": "gpt-5", "requires_key": True},
    {"name": "google", "default_model": "gemini-2.5-pro", "requires_key": True},
    {"name": "grok", "default_model": "grok-3", "requires_key": True},
    {"name": "ollama", "default_model": "gemma4", "requires_key": False},
    {"name": "stub", "default_model": "stub", "requires_key": False},
]

COLOR_OPTIONS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "cyan",
    "pink",
    "yellow",
    "teal",
    "indigo",
]


@app.get("/providers")
async def providers() -> dict:
    return {"providers": PROVIDER_DEFAULTS, "colors": COLOR_OPTIONS}


@app.post("/api-keys")
async def create_api_key(body: dict) -> dict:
    from app.models.api_key import store_key

    provider = body.get("provider", "")
    label = body.get("label", provider)
    raw_key = body.get("key", "")
    if not raw_key:
        return {"error": "key is required"}
    async with SessionLocal() as session:
        key_id = await store_key(session, provider, label, raw_key)
        await session.commit()
    return {"id": key_id, "provider": provider, "label": label}


@app.get("/api-keys")
async def get_api_keys() -> dict:
    from app.models.api_key import list_keys

    async with SessionLocal() as session:
        keys = await list_keys(session)
    return {"keys": keys}


@app.delete("/api-keys/{key_id}")
async def remove_api_key(key_id: int) -> dict:
    from app.models.api_key import delete_key

    async with SessionLocal() as session:
        ok = await delete_key(session, key_id)
        await session.commit()
    return {"deleted": ok}


@app.post("/configure")
async def configure_simulation(body: dict) -> dict:
    """Set up a new simulation with a dynamic agent roster."""
    from app.agents.factory import build_agents
    from app.models.api_key import get_key
    from app.thought_export import start_export

    global _current_turn, _active_roster

    agents_list = body.get("agents", [])
    settings = get_settings()
    if not (settings.min_agents <= len(agents_list) <= settings.max_agents):
        return {
            "error": f"Need {settings.min_agents}-{settings.max_agents} agents, got {len(agents_list)}"
        }

    # Validate + resolve API keys
    roster: list[dict] = []
    for a in agents_list:
        agent_id = a.get("agent_id", "").lower().replace(" ", "_")
        if not agent_id:
            return {"error": "Each agent needs an agent_id"}
        # Auto-generate personality if empty/missing
        personality = (a.get("personality") or "").strip()
        if not personality:
            _auto_personalities = [
                "Adaptive strategist who reads the room and adjusts tactics each turn.",
                "Cautious optimizer who minimizes risk and builds steady wealth.",
                "Bold opportunist who takes big swings and exploits market gaps.",
                "Social connector who builds alliances and leverages relationships.",
                "Calculating survivalist who hoards resources and strikes when advantageous.",
            ]
            personality = _auto_personalities[len(roster) % len(_auto_personalities)]
        spec = {
            "agent_id": agent_id,
            "display_name": a.get("display_name", agent_id.upper()),
            "provider": a.get("provider", "stub"),
            "model": a.get("model", ""),
            "personality": personality,
            "sprite": a.get("sprite", "robot"),
        }
        # Resolve API key: either inline or from stored key
        api_key_id = a.get("api_key_id")
        inline_key = a.get("api_key", "")
        if api_key_id:
            async with SessionLocal() as session:
                key = await get_key(session, int(api_key_id))
            if key:
                spec["api_key"] = key
        elif inline_key:
            spec["api_key"] = inline_key
        roster.append(spec)

    # Check for duplicate agent_ids
    ids = [r["agent_id"] for r in roster]
    if len(set(ids)) != len(ids):
        return {"error": "Duplicate agent_id found"}

    # Reset DB tables and re-seed
    from app.db import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await seed_roster(session, roster=roster)

    _active_roster = roster
    _current_turn = 0
    start_export()

    # Broadcast new state
    snapshot = await state()
    await broadcaster.broadcast({"event": "snapshot", "snapshot": snapshot})

    return {"agent_count": len(roster), "agents": ids}


@app.get("/state")
async def state() -> dict:
    async with SessionLocal() as session:
        agents = (await session.execute(select(Agent))).scalars().all()
        recent = (
            (
                await session.execute(
                    select(ThoughtLog).order_by(desc(ThoughtLog.id)).limit(20)
                )
            )
            .scalars()
            .all()
        )
    return {
        "turn": _current_turn,
        "agents": [
            {
                "agent_id": a.agent_id,
                "display_name": a.display_name,
                "provider": a.provider,
                "balance": a.balance,
                "alive": a.alive,
                "spouse": a.spouse_id,
                "allies": list(a.allies or []),
                "enemies": list(a.enemies or []),
                "sprite": a.sprite,
                "pos_x": a.pos_x,
                "pos_y": a.pos_y,
                "consecutive_errors": a.consecutive_errors,
                "last_error": a.last_error,
                "trust_score": a.trust_score,
                "steal_count": a.steal_count,
                "inventory": a.inventory or {},
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


@app.get("/ledger")
async def ledger(limit: int = 100) -> dict:
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(Transaction).order_by(desc(Transaction.id)).limit(limit)
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


@app.get("/events")
async def events(limit: int = 50) -> dict:
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(WorldEvent).order_by(desc(WorldEvent.id)).limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return {
        "events": [{"turn": e.turn, "kind": e.kind, "payload": e.payload} for e in rows]
    }


@app.post("/turn")
async def step_turn() -> dict:
    """Drive a single turn of the simulation. Useful for manual stepping/debug."""
    from app.agents.factory import build_agents  # avoid import-time cycles

    global _current_turn
    async with _turn_lock:
        _current_turn += 1
        agents = build_agents(roster=_active_roster)
        async with SessionLocal() as session:
            result = await run_turn(session, turn=_current_turn, agents=agents)
        snapshot = await state()
        if result.paused:
            await broadcaster.broadcast(
                {
                    "event": "simulation_paused",
                    "turn": _current_turn,
                    "agent_id": result.pause_agent_id,
                    "reason": result.pause_reason,
                    "snapshot": snapshot,
                }
            )
            return {
                "turn": result.turn,
                "paused": True,
                "agent_id": result.pause_agent_id,
                "reason": result.pause_reason,
            }
        await broadcaster.broadcast(
            {"event": "turn", "turn": _current_turn, "snapshot": snapshot}
        )
    return {
        "turn": result.turn,
        "apex": result.apex_declared,
        "eliminated": result.eliminated,
    }


@app.post("/reset")
async def reset_simulation() -> dict:
    """Drop all data and return to a clean state. User must reconfigure."""
    from app.thought_export import stop_export

    global _current_turn, _active_roster
    from app.db import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    _current_turn = 0
    _active_roster = None
    stop_export()
    snapshot = await state()
    await broadcaster.broadcast({"event": "snapshot", "snapshot": snapshot})
    return {"reset": True}


@app.post("/run")
async def run_many(turns: int = 10) -> dict:
    """Run N turns in sequence. Returns when finished, apex declared, or paused on error."""
    from app.agents.factory import build_agents

    global _current_turn
    settings = get_settings()
    cap = min(turns, settings.max_turns)
    apex = None
    eliminated: list[str] = []
    agents = build_agents(roster=_active_roster)
    async with _turn_lock:
        for _ in range(cap):
            _current_turn += 1
            async with SessionLocal() as session:
                result = await run_turn(session, turn=_current_turn, agents=agents)
            snapshot = await state()
            if result.paused:
                await broadcaster.broadcast(
                    {
                        "event": "simulation_paused",
                        "turn": _current_turn,
                        "agent_id": result.pause_agent_id,
                        "reason": result.pause_reason,
                        "snapshot": snapshot,
                    }
                )
                return {
                    "final_turn": _current_turn,
                    "apex": None,
                    "eliminated": eliminated,
                    "paused": True,
                    "agent_id": result.pause_agent_id,
                    "reason": result.pause_reason,
                }
            await broadcaster.broadcast(
                {"event": "turn", "turn": _current_turn, "snapshot": snapshot}
            )
            eliminated.extend(result.eliminated)
            if result.apex_declared:
                apex = result.apex_declared
                break
    return {"final_turn": _current_turn, "apex": apex, "eliminated": eliminated}


@app.get("/export/thoughts")
async def export_thoughts() -> FileResponse:
    """Download the current thought log as JSONL."""
    from app.thought_export import get_exporter

    exporter = get_exporter()
    if exporter is None or not exporter.filepath.exists():
        return FileResponse(path="/dev/null", status_code=404)
    return FileResponse(
        path=str(exporter.filepath),
        media_type="application/x-ndjson",
        filename=exporter.filepath.name,
    )


@app.get("/export/thoughts/latest")
async def export_thoughts_latest(lines: int = 50) -> dict:
    """Return the last N thought entries from the current log."""
    from app.thought_export import get_exporter

    exporter = get_exporter()
    if exporter is None:
        return {"entries": []}
    return {"entries": exporter.tail(lines)}


@app.post("/agents/{agent_id}/remove")
async def remove_agent(agent_id: str) -> dict:
    """Force-eliminate a failing agent so the simulation can continue."""
    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            return {"error": "agent not found"}
        agent.alive = False
        agent.eliminated_at_turn = _current_turn
        agent.consecutive_errors = 0
        agent.last_error = None
        session.add(
            WorldEvent(
                turn=_current_turn,
                kind="provider_failure",
                payload={"agent_id": agent_id, "removed_by_user": True},
            )
        )
        await session.commit()
    snapshot = await state()
    await broadcaster.broadcast(
        {"event": "turn", "turn": _current_turn, "snapshot": snapshot}
    )
    return {"removed": agent_id, "turn": _current_turn}


@app.post("/simulation/resume")
async def resume_simulation() -> dict:
    """Clear error counters for all agents so the simulation can resume."""
    async with SessionLocal() as session:
        agents = (
            (await session.execute(select(Agent).where(Agent.alive.is_(True))))
            .scalars()
            .all()
        )
        for a in agents:
            a.consecutive_errors = 0
            a.last_error = None
        await session.commit()
    return {"resumed": True, "turn": _current_turn}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await broadcaster.connect(ws)
    try:
        # send initial snapshot
        snapshot = await state()
        await ws.send_json({"event": "snapshot", "snapshot": snapshot})
        while True:
            # keep connection alive; ignore client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(ws)
