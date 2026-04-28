from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models.agent import Agent
from app.models.ledger import ThoughtLog, Transaction, WorldEvent
from app.oracle.engine import run_turn, seed_roster
from app.ws import broadcaster

log = logging.getLogger("darwin")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    await init_db()
    async with SessionLocal() as session:
        await seed_roster(session)
    yield


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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/state")
async def state() -> dict:
    async with SessionLocal() as session:
        agents = (await session.execute(select(Agent))).scalars().all()
        recent = (
            await session.execute(select(ThoughtLog).order_by(desc(ThoughtLog.id)).limit(20))
        ).scalars().all()
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
            }
            for a in agents
        ],
        "recent_thoughts": [
            {
                "turn": t.turn,
                "agent_id": t.agent_id,
                "monologue": t.monologue,
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
            await session.execute(select(Transaction).order_by(desc(Transaction.id)).limit(limit))
        ).scalars().all()
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
            await session.execute(select(WorldEvent).order_by(desc(WorldEvent.id)).limit(limit))
        ).scalars().all()
    return {"events": [{"turn": e.turn, "kind": e.kind, "payload": e.payload} for e in rows]}


@app.post("/turn")
async def step_turn() -> dict:
    """Drive a single turn of the simulation. Useful for manual stepping/debug."""
    from app.agents.factory import build_agents  # avoid import-time cycles

    global _current_turn
    async with _turn_lock:
        _current_turn += 1
        agents = build_agents()
        async with SessionLocal() as session:
            result = await run_turn(session, turn=_current_turn, agents=agents)
        snapshot = await state()
        await broadcaster.broadcast({"event": "turn", "turn": _current_turn, "snapshot": snapshot})
    return {"turn": result.turn, "apex": result.apex_declared, "eliminated": result.eliminated}


@app.post("/run")
async def run_many(turns: int = 10) -> dict:
    """Run N turns in sequence. Returns when finished or apex declared."""
    from app.agents.factory import build_agents

    global _current_turn
    settings = get_settings()
    cap = min(turns, settings.max_turns)
    apex = None
    eliminated: list[str] = []
    agents = build_agents()
    async with _turn_lock:
        for _ in range(cap):
            _current_turn += 1
            async with SessionLocal() as session:
                result = await run_turn(session, turn=_current_turn, agents=agents)
            snapshot = await state()
            await broadcaster.broadcast({"event": "turn", "turn": _current_turn, "snapshot": snapshot})
            eliminated.extend(result.eliminated)
            if result.apex_declared:
                apex = result.apex_declared
                break
    return {"final_turn": _current_turn, "apex": apex, "eliminated": eliminated}


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
