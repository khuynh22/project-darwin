# Pack 0 — Venue-Gated Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An agent is offered only the actions at the building it stands in, plus `travel`, so filling fourteen more venues does not grow the per-wake prompt.

**Architecture:** Gating is a run flag, `venue_gating`, defaulting to `False`. With it off, every existing code path behaves exactly as today and `travel` does not exist in the tool list at all — that keeps the 25-action world frozen as a comparable condition. With it on, `_tools_for_openai` filters by the agent's venue, the engine stops deriving a venue from the action, and an action taken where it is unavailable is recorded as a failure instead of mutating the world.

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy, Pydantic v2, pytest + pytest-asyncio. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-24-venue-content-packs-design.md`

## Global Constraints

- Money always `round(x, 2)`. Goods are integers.
- All DB calls async. No sync SQLAlchemy anywhere.
- Never hardcode agent ids, sprite names, or model ids.
- Do not import `agents/factory` at module level in `engine.py` (lazy import).
- All mutations go through `actions.py` + `engine.py`. Nothing bypasses the Oracle.
- `shared/` is the single source of truth: an action is declared in `shared/actions.json`, listed on its venue in `shared/venues.json`, given a Pydantic model in `oracle/schemas.py`, a handler in `oracle/actions.py`, and a stub bias in `agents/stub.py`. `tests/test_world_data.py` fails if any is missing.
- Free actions must take exactly `0.0` beats; `world_data._validate` raises otherwise.
- `venue_gating` defaults to `False` everywhere it appears. A run that does not ask for gating must produce a byte-identical trace to one recorded before this branch.
- Run tests from `backend/`: `cd backend && python -m pytest ...`.

## Review Focus

Five conditions the spec implies that no task's happy path exercises. Each has a test added to the task that owns the code.

1. **A `travel` target that is planned, unknown, or empty.** `shared/venues.json` has fourteen `planned` venues with coordinates; `VENUE_POS` contains them, so `travel_ticks` will happily compute a walk to the Courthouse. Travelling to a building that does not exist yet must be rejected, not silently allowed. → Task 2.
2. **An agent row whose `venue` is NULL or a stale id.** `db.py` back-fills `'plaza'`, but a row written by an older build, or a venue id retired later, must degrade to the Plaza rather than raise. → Task 4.
3. **A model that returns no tool call at all while gating is on.** `openai_agent` currently falls back to `work`, which is illegal anywhere but the Work Site. Left alone it would produce an endless rejection loop for an agent standing in the Bank. → Task 3.
4. **A rejected action must still cost deliberation and still be recorded.** Otherwise a model can probe the action space for free and the trace loses the attempt, which is the signal we said we wanted to keep. → Task 4.
5. **A trace replayed under the opposite flag.** Replay must read `venue_gating` from the trace's manifest, never from the current build's default. → Task 7.

---

### Task 1: The `anywhere` venue and the `travel` row

An action callable from every venue breaks the SSOT ownership rule. `world_data._validate` walks every venue's `actions` list, records an owner per action, then raises `actions with no venue: [...]` for anything unowned. `travel` will be owned by nobody, so the validator needs one explicit exemption rather than a special case scattered across callers.

**Files:**
- Modify: `shared/actions.json` (append one row)
- Modify: `backend/app/oracle/world_data.py:116-170` (`_validate`, exports)
- Test: `backend/tests/test_world_data.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `world_data.ANYWHERE: str = "anywhere"`, `world_data.UBIQUITOUS_ACTIONS: frozenset[str]` (actions whose venue is `anywhere`), and `world_data.actions_at(venue: str, *, gated: bool) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_world_data.py`:

```python
def test_travel_is_owned_by_no_venue():
    import app.oracle.world_data as wd

    assert wd.ACTIONS["travel"].venue == wd.ANYWHERE
    assert wd.UBIQUITOUS_ACTIONS == frozenset({"travel"})
    for venue in wd.VENUES.values():
        assert "travel" not in venue.actions


def test_actions_at_a_venue_adds_the_ubiquitous_ones_only_when_gated():
    import app.oracle.world_data as wd

    gated = wd.actions_at("bank", gated=True)
    assert "invest" in gated
    assert "travel" in gated
    assert "steal" not in gated

    ungated = wd.actions_at("bank", gated=False)
    assert set(ungated) == set(wd.ACTIONS) - {"travel"}


def test_an_unknown_venue_offers_only_the_ubiquitous_actions():
    import app.oracle.world_data as wd

    assert wd.actions_at("atlantis", gated=True) == ["travel"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_world_data.py -k "travel or actions_at or ubiquitous" -v`
Expected: FAIL — `AttributeError: module 'app.oracle.world_data' has no attribute 'ANYWHERE'`

- [ ] **Step 3: Add the SSOT row**

Append to `shared/actions.json`, inside the top-level array:

```json
  {
    "id": "travel",
    "tier": "major",
    "family": "movement",
    "venue": "anywhere",
    "beats": 0.0,
    "emoji": "🚶",
    "intent": "to walk",
    "summary": "Walk to another building. The walk is the whole action -- you arrive and act next time you wake."
  }
```

`beats` is `0.0` because travel's real duration is the walk, which the engine charges with `travel_ticks(from, to)`. This is the one row where the `beats` column is not the action's duration; Task 4 is where that is charged.

- [ ] **Step 4: Exempt it in `world_data.py`**

In `backend/app/oracle/world_data.py`, above `_validate`:

```python
#: Venue value for an action callable from every building. Exactly one action
#: uses it (``travel``): gating has to leave a way out of a room, and giving
#: that way out a fake home venue would make it gateable by accident.
ANYWHERE: Final[str] = "anywhere"
```

Add `from typing import Final` to the existing `typing` import if absent.

In `_validate`, skip ubiquitous actions when collecting owners and when checking for orphans:

```python
    ubiquitous = {aid for aid, row in ACTIONS.items() if row.venue == ANYWHERE}
    missing = set(ACTIONS) - set(owner) - ubiquitous
    if missing:
        raise ValueError(f"actions with no venue: {sorted(missing)}")
    for action in ACTIONS.values():
        if action.id in ubiquitous:
            continue
        if action.venue != owner[action.id]:
            raise ValueError(
                f"{action.id} claims {action.venue}, listed at {owner[action.id]}"
            )
        if action.tier == "free" and action.beats != 0.0:
            raise ValueError(f"free action {action.id} must take zero beats")
```

Keep the `free action must take zero beats` check applying to ubiquitous actions too by moving it above the `continue`:

```python
    for action in ACTIONS.values():
        if action.tier == "free" and action.beats != 0.0:
            raise ValueError(f"free action {action.id} must take zero beats")
        if action.id in ubiquitous:
            continue
        if action.venue != owner[action.id]:
            raise ValueError(
                f"{action.id} claims {action.venue}, listed at {owner[action.id]}"
            )
```

After `_validate()` runs, beside the other derived tables:

```python
UBIQUITOUS_ACTIONS: frozenset[str] = frozenset(
    aid for aid, row in ACTIONS.items() if row.venue == ANYWHERE
)


def actions_at(venue: str, *, gated: bool) -> list[str]:
    """Action ids an agent standing at *venue* may call.

    Ungated, every action except the ubiquitous ones, which exist only to move
    an agent that has nothing else available. Including ``travel`` in an ungated
    run would change the 25-action baseline the frozen probes are measured
    against.
    """
    if not gated:
        return [aid for aid in ACTIONS if aid not in UBIQUITOUS_ACTIONS]
    here = VENUE_ACTIONS.get(venue, [])
    return [*here, *sorted(UBIQUITOUS_ACTIONS)]
```

Add `"ANYWHERE"`, `"UBIQUITOUS_ACTIONS"`, and `"actions_at"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_world_data.py -v`
Expected: PASS, all tests in the file — the existing invariants must survive the new row.

- [ ] **Step 6: Commit**

```bash
git add shared/actions.json backend/app/oracle/world_data.py backend/tests/test_world_data.py
git commit -m "feat(oracle): a travel action owned by no venue"
```

---

### Task 2: `travel` argument model and handler

**Files:**
- Modify: `backend/app/oracle/schemas.py` (new `TravelArgs`, `ARG_MODELS` entry)
- Modify: `backend/app/oracle/actions.py` (new `do_travel`, `ACTION_TABLE` entry)
- Test: `backend/tests/test_travel_action.py` (create)

**Interfaces:**
- Consumes: `world_data.ANYWHERE` (Task 1).
- Produces: `schemas.TravelArgs` with field `venue: str`; `actions.do_travel(session, *, session_id: str, turn: int, actor_id: str, venue: str) -> ActionResult`.

`do_travel` validates and records. It does **not** move the agent: the engine owns position because it also owns the clock, and splitting that would let a handler move an agent without charging the walk. A successful `do_travel` is the engine's licence to move it.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_travel_action.py`:

```python
"""The travel action: what it accepts, and what it refuses to do."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models.agent import Agent
from app.oracle.actions import ACTION_TABLE, do_travel

SID = "trv"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(
            Agent(
                session_id=SID,
                agent_id="red",
                display_name="Red",
                provider="stub",
                personality="x",
                sprite="red",
                venue="plaza",
            )
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_travelling_to_a_built_venue_is_accepted(session):
    result = await do_travel(
        session, session_id=SID, turn=1, actor_id="red", venue="alley"
    )

    assert result.success


async def test_travelling_to_where_you_already_stand_is_rejected(session):
    result = await do_travel(
        session, session_id=SID, turn=1, actor_id="red", venue="plaza"
    )

    assert not result.success
    assert "already" in result.note


@pytest.mark.parametrize("target", ["courthouse", "atlantis", ""])
async def test_travelling_to_an_unbuilt_or_unknown_venue_is_rejected(session, target):
    result = await do_travel(
        session, session_id=SID, turn=1, actor_id="red", venue=target
    )

    assert not result.success
    assert "no such building" in result.note


async def test_travel_is_registered_in_the_action_table():
    assert ACTION_TABLE["travel"] is do_travel
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_travel_action.py -v`
Expected: FAIL — `ImportError: cannot import name 'do_travel' from 'app.oracle.actions'`

- [ ] **Step 3: Add the argument model**

In `backend/app/oracle/schemas.py`, beside the other argument models:

```python
class TravelArgs(_BaseArgs):
    venue: str = Field(
        ..., description="id of the building to walk to, as printed in ELSEWHERE"
    )
```

Register it in `ARG_MODELS`:

```python
    "travel": TravelArgs,
```

The field is a plain `str`, not a `Literal` over built venue ids, for the same reason `target` is: the set is data in `shared/`, and freezing it into a type would put the roster in the schema. The handler rejects anything unbuilt.

- [ ] **Step 4: Add the handler**

In `backend/app/oracle/actions.py`, beside the other handlers:

```python
async def do_travel(
    session: AsyncSession, *, session_id: str, turn: int, actor_id: str, venue: str
) -> ActionResult:
    """Accept or refuse a walk. The engine does the moving and charges the walk.

    Planned venues are in ``VENUE_POS`` because their coordinates are reserved,
    so ``travel_ticks`` would compute a perfectly good walk to a building that
    has nothing in it. Built-only is therefore checked here rather than relying
    on the distance lookup to fail.
    """
    from app.oracle.world_data import BUILT_VENUES

    actor = await _get_agent(session, session_id, actor_id)
    if actor is None or not actor.alive:
        return ActionResult(False, "actor not alive")
    if venue not in BUILT_VENUES:
        return ActionResult(False, f"no such building: {venue!r}")
    if venue == (actor.venue or DEFAULT_VENUE):
        return ActionResult(False, f"already at {venue}")
    await _record(
        session,
        session_id=session_id,
        turn=turn,
        actor_id=actor_id,
        target_id=None,
        action="travel",
        delta=0,
        payload={"from": actor.venue or DEFAULT_VENUE, "to": venue},
        note=f"walking from {actor.venue or DEFAULT_VENUE} to {venue}",
    )
    return ActionResult(True, f"walking to {venue}")
```

Import `DEFAULT_VENUE` from `app.oracle.space` at the top of `actions.py` if it is not already imported. Register the handler:

```python
    "travel": do_travel,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_travel_action.py tests/test_world_data.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/oracle/schemas.py backend/app/oracle/actions.py backend/tests/test_travel_action.py
git commit -m "feat(oracle): travel accepts a built venue and refuses the rest"
```

---

### Task 3: Venue-gated tool list and prompt

**Files:**
- Modify: `backend/app/agents/base.py` (`render_venue_block`)
- Modify: `backend/app/agents/openai_agent.py` (`_tools_for_openai`, `decide`)
- Test: `backend/tests/test_venue_prompt.py`, `backend/tests/test_gated_tools.py` (create)

**Interfaces:**
- Consumes: `world_data.actions_at(venue, gated=...)` (Task 1).
- Produces: `openai_agent._tools_for_openai(venue: str | None = None, *, gated: bool = False) -> list[dict]`; `base.render_venue_block(current_venue: str, *, gated: bool = False) -> str`. `state["_venue_gating"]: bool` is the flag's name inside the prompt state dict, set by Task 4.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gated_tools.py`:

```python
"""Which tools an agent is offered, and what it falls back to when it offers none."""

from __future__ import annotations

from app.agents.openai_agent import _tools_for_openai, _venue_fallback


def _names(tools: list[dict]) -> set[str]:
    return {t["function"]["name"] for t in tools}


def test_ungated_offers_every_action_except_travel():
    import app.oracle.world_data as wd

    assert _names(_tools_for_openai()) == set(wd.ACTIONS) - {"travel"}


def test_gated_offers_this_venue_plus_travel():
    assert _names(_tools_for_openai("bank", gated=True)) == {
        "invest",
        "lend",
        "audit",
        "will",
        "travel",
    }


def test_gated_at_the_plaza_offers_only_travel():
    assert _names(_tools_for_openai("plaza", gated=True)) == {"travel"}


def test_the_fallback_walks_toward_the_action_it_wanted():
    action, arguments = _venue_fallback("steal", venue="bank")

    assert action == "travel"
    assert arguments == {"venue": "alley"}


def test_the_fallback_from_nowhere_in_particular_still_moves():
    action, arguments = _venue_fallback(None, venue="plaza")

    assert action == "travel"
    assert arguments["venue"] in {"market", "bank", "lounge", "work", "alley", "casino"}
```

Append to `backend/tests/test_venue_prompt.py`:

```python
def test_the_gated_block_says_how_to_leave():
    block = render_venue_block("bank", gated=True)

    assert "travel(" in block
    assert "invest(" in block
    # Other venues' actions are still named -- that is the reason to walk there.
    assert "steal" in block.split("ELSEWHERE")[1]


def test_the_ungated_block_is_unchanged():
    assert render_venue_block("bank") == render_venue_block("bank", gated=False)
    assert "travel(" not in render_venue_block("bank")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_gated_tools.py tests/test_venue_prompt.py -v`
Expected: FAIL — `ImportError: cannot import name '_venue_fallback'`

- [ ] **Step 3: Gate the tool list and add the fallback**

In `backend/app/agents/openai_agent.py`, replace `_tools_for_openai`:

```python
def _tools_for_openai(venue: str | None = None, *, gated: bool = False) -> list[dict]:
    available = set(actions_at(venue or DEFAULT_VENUE, gated=gated))
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_DEFINITIONS
        if t["name"] in available
    ]


def _venue_fallback(wanted: str | None, *, venue: str) -> tuple[str, dict]:
    """What to do when a gated model offers nothing usable.

    Falling back to ``work`` is what the ungated client does, and under gating it
    is illegal everywhere but the Work Site -- an agent in the Bank would be
    rejected every wake forever. Walking toward whatever it asked for is both
    legal and a reasonable reading of the intent; with no intent to read, walk
    to the nearest other building rather than stand still.
    """
    from app.oracle.space import travel_ticks
    from app.oracle.world_data import ACTIONS, BUILT_VENUES, UBIQUITOUS_ACTIONS

    row = ACTIONS.get(wanted or "")
    if row is not None and row.id not in UBIQUITOUS_ACTIONS and row.venue != venue:
        return "travel", {"venue": row.venue}
    others = [vid for vid, v in BUILT_VENUES.items() if vid != venue and v.actions]
    nearest = min(others, key=lambda vid: travel_ticks(venue, vid))
    return "travel", {"venue": nearest}
```

Add the imports at the top of the module:

```python
from app.oracle.space import DEFAULT_VENUE
from app.oracle.world_data import actions_at
```

In `decide`, read the flag and the venue from state, pass them to the tool list, and use the new fallback:

```python
        gated = bool(state.get("_venue_gating"))
        venue = state.get("_venue") or DEFAULT_VENUE
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=_tools_for_openai(venue, gated=gated),
            tool_choice="auto",
            max_tokens=self.max_tokens,
        )
        choice = resp.choices[0]
        monologue = (choice.message.content or "").strip()
        tool_calls = choice.message.tool_calls or []
        if not tool_calls:
            if gated:
                action, arguments = _venue_fallback(None, venue=venue)
                return AgentDecision(
                    action, arguments,
                    monologue=monologue or "(no tool -- walking on)",
                )
            return AgentDecision("work", {}, monologue=monologue or "(no tool -- falling back to work)")
```

- [ ] **Step 4: Gate the prompt block**

In `backend/app/agents/base.py`, change `render_venue_block`'s signature to `render_venue_block(current_venue: str, *, gated: bool = False) -> str` and change the ELSEWHERE header when gated:

```python
    lines.append("")
    if gated:
        lines.append(
            "ELSEWHERE (travel(venue) to walk there; cost in beats from here):"
        )
    else:
        lines.append("ELSEWHERE (walk cost in beats from here):")
```

And when gated, name the way out under the current venue's actions:

```python
    if gated:
        lines.append(
            f"  {'travel(venue)'.ljust(pad if venue.actions else 18)} "
            f"{ACTIONS['travel'].summary}"
        )
```

Place that immediately after the loop over `venue.actions` (and after the "Nothing to do here" line, so the Plaza also shows it). In `render_world_brief`, pass the flag through:

```python
        render_venue_block(state.get("_venue", "plaza"), gated=bool(state.get("_venue_gating"))),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_gated_tools.py tests/test_venue_prompt.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/openai_agent.py backend/app/agents/base.py backend/tests/test_gated_tools.py backend/tests/test_venue_prompt.py
git commit -m "feat(agents): the prompt offers the building you are standing in"
```

---

### Task 4: The engine stops deriving a venue from the action

**Files:**
- Modify: `backend/app/oracle/event_engine.py:168-180` (signature), `:225-285` (state, application, movement)
- Test: `backend/tests/test_venue_gating_engine.py` (create)

**Interfaces:**
- Consumes: `world_data.actions_at` (Task 1), `do_travel` via `ACTION_TABLE` (Task 2), `state["_venue_gating"]` (Task 3).
- Produces: `run_events(..., venue_gating: bool = False)`; the outcome string `"not available here [rejected]"` for an action unavailable at the agent's venue.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_venue_gating_engine.py`:

```python
"""Gating, from the engine's side: what moves, what is refused, what it costs."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import AgentDecision, BaseAgent
from app.db import Base
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.event_engine import run_events

SID = "gate"


class Scripted(BaseAgent):
    provider = "scripted"

    def __init__(self, agent_id: str, *, script: list[tuple[str, dict]], wake_after: float = 1.0):
        super().__init__(agent_id, "scripted")
        self.script = list(script)
        self.wake_after = wake_after

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        action, arguments = self.script[0] if len(self.script) == 1 else self.script.pop(0)
        return AgentDecision(action, dict(arguments), wake_after=self.wake_after)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for aid in ("red", "blue"):
            s.add(
                Agent(
                    session_id=SID,
                    agent_id=aid,
                    display_name=aid.title(),
                    provider="stub",
                    personality="x",
                    sprite=aid,
                    balance=10.0,
                    venue="plaza",
                )
            )
        await s.commit()
        yield s
    await engine.dispose()


async def _outcomes(session) -> list[str]:
    rows = (
        await session.execute(
            select(ThoughtLog).where(ThoughtLog.session_id == SID).order_by(ThoughtLog.id)
        )
    ).scalars().all()
    return [r.outcome for r in rows]


async def test_an_action_from_the_wrong_venue_is_refused_and_recorded(session):
    agents = {
        "red": Scripted("red", script=[("steal", {"target": "blue"})]),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=4, venue_gating=True
    )

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue == "plaza"
    assert any("not available here" in o for o in await _outcomes(session))


async def test_travel_moves_the_agent_and_then_the_action_lands(session):
    agents = {
        "red": Scripted(
            "red",
            script=[("travel", {"venue": "alley"}), ("steal", {"target": "blue"})],
        ),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=12, venue_gating=True
    )

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue == "alley"
    outcomes = await _outcomes(session)
    assert any("walking to alley" in o for o in outcomes)
    assert not any("not available here" in o for o in outcomes)


async def test_a_stale_venue_degrades_to_the_plaza(session):
    row = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    row.venue = "atlantis"
    await session.commit()

    agents = {
        "red": Scripted("red", script=[("travel", {"venue": "market"})]),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=6, venue_gating=True
    )

    assert any("walking to market" in o for o in await _outcomes(session))


async def test_ungated_runs_still_derive_the_venue_from_the_action(session):
    agents = {
        "red": Scripted("red", script=[("steal", {"target": "blue"})]),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(session, session_id=SID, agents=agents, horizon_beats=4)

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue == "alley"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_venue_gating_engine.py -v`
Expected: FAIL — `TypeError: run_events() got an unexpected keyword argument 'venue_gating'`

- [ ] **Step 3: Thread the flag and split the movement rule**

In `backend/app/oracle/event_engine.py`, add the parameter to `run_events`:

```python
    condition: str = "neutral",
    venue_gating: bool = False,
    max_events: int | None = None,
```

Put it in the prompt state beside the venue:

```python
        state["_venue"] = at_venue.get(event.agent_id, DEFAULT_VENUE)
        state["_venue_gating"] = venue_gating
```

Normalise a stale venue when the roster is read, so everything downstream sees a real building:

```python
        at_venue[db_agent.agent_id] = (
            db_agent.venue if db_agent.venue in BUILT_VENUES else DEFAULT_VENUE
        )
```

(`BUILT_VENUES` comes from `app.oracle.world_data`; add the import.)

Before applying the decision, refuse an unavailable action when gating is on:

```python
        here = at_venue.get(event.agent_id, DEFAULT_VENUE)
        if venue_gating and decision.action not in actions_at(here, gated=True):
            outcome = f"{decision.action} not available here [rejected]"
        else:
            outcome = await _apply_decision(
                session,
                session_id=session_id,
                turn=event.agent_seq,
                agent=db_agent,
                decision=decision,
                rng=rng,
            )
```

Gate the free action the same way, so the free tier is not the loophole:

```python
        if decision.free_action:
            free_ok = not venue_gating or decision.free_action in actions_at(
                here, gated=True
            )
            if free_ok:
                free = AgentDecision(
                    action=decision.free_action, arguments=decision.free_arguments
                )
                await _apply_decision(
                    session,
                    session_id=session_id,
                    turn=event.agent_seq,
                    agent=db_agent,
                    decision=free,
                    rng=rng,
                )
```

Replace the movement block. Ungated keeps deriving the venue from the action; gated moves only on an accepted `travel`:

```python
        if venue_gating:
            from_venue = here
            moved = decision.action == "travel" and "[rejected]" not in outcome
            venue = decision.arguments.get("venue", here) if moved else here
            travel = travel_ticks(from_venue, venue)
        else:
            venue = venue_for(decision.action)
            from_venue = at_venue.get(event.agent_id, venue)
            travel = travel_ticks(from_venue, venue)
        at_venue[event.agent_id] = venue
        db_agent.venue = venue
```

Deliberation is charged outside this branch already, so a rejected action still costs thinking time — leave `busy` as it is:

```python
        busy = travel + commit_ticks(
            decision.action,
            reasoning_tokens=decision.reasoning_tokens,
            completion_tokens=decision.completion_tokens,
        )
```

Add `actions_at` to the `world_data` import at the top of the module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_venue_gating_engine.py tests/test_event_engine.py tests/test_continuous_time.py -v`
Expected: PASS. `test_event_engine.py` must pass untouched — it runs ungated, which is the default.

- [ ] **Step 5: Commit**

```bash
git add backend/app/oracle/event_engine.py backend/tests/test_venue_gating_engine.py
git commit -m "feat(oracle): under gating, only travel moves an agent"
```

---

### Task 5: The stub agent respects the building it is in

`StubAgent` rolls over `DEFAULT_BIAS`, which names all 25 actions. Under gating it would spend most wakes proposing actions that are rejected, which makes every stub-driven gated test meaningless and hides the diversity regression the spec asks us to watch for.

**Files:**
- Modify: `backend/app/agents/stub.py` (`_pick_major`, free-action pick, `DEFAULT_BIAS`)
- Test: `backend/tests/test_stub_gating.py` (create)

**Interfaces:**
- Consumes: `world_data.actions_at` (Task 1), `state["_venue_gating"]` and `state["_venue"]` (Tasks 3-4).
- Produces: no new public names. `DEFAULT_BIAS` gains `"travel": 3`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_stub_gating.py`:

```python
"""A gated stub only proposes what the building it stands in offers."""

from __future__ import annotations

import random

from app.agents.stub import DEFAULT_BIAS, StubAgent
from app.models.agent import Agent
from app.oracle.world_data import actions_at


def _agent() -> Agent:
    return Agent(
        session_id="s",
        agent_id="red",
        display_name="Red",
        provider="stub",
        personality="x",
        sprite="red",
        balance=10.0,
        venue="plaza",
    )


def _state(venue: str) -> dict:
    return {
        "turn": 1,
        "agents": [{"agent_id": "red", "balance": 10.0, "alive": True}],
        "_venue": venue,
        "_venue_gating": True,
    }


def test_travel_has_a_bias_weight():
    assert DEFAULT_BIAS["travel"] > 0


def test_a_gated_stub_at_the_plaza_can_only_travel():
    from app.oracle.world_data import BUILT_VENUES

    stub = StubAgent(agent_id="red", model="stub")
    for seed in range(50):
        decision = stub._pick_major(_state("plaza"), _agent(), random.Random(seed))
        assert decision.action == "travel"
        assert decision.arguments["venue"] in BUILT_VENUES
        assert decision.arguments["venue"] != "plaza"


def test_a_gated_stub_in_the_bank_stays_inside_the_bank_menu():
    stub = StubAgent(agent_id="red", model="stub")
    allowed = set(actions_at("bank", gated=True))
    for seed in range(50):
        decision = stub._pick_major(_state("bank"), _agent(), random.Random(seed))
        assert decision.action in allowed


def test_an_ungated_stub_is_unchanged():
    stub = StubAgent(agent_id="red", model="stub")
    state = {
        "turn": 1,
        "agents": [{"agent_id": "red", "balance": 10.0, "alive": True}],
        "_venue": "plaza",
    }
    seen = {
        stub._pick_major(state, _agent(), random.Random(seed)).action
        for seed in range(200)
    }
    assert "travel" not in seen
    assert len(seen) > 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_stub_gating.py -v`
Expected: FAIL — `KeyError: 'travel'` on `DEFAULT_BIAS["travel"]`

- [ ] **Step 3: Filter the roll by venue**

In `backend/app/agents/stub.py`, add the weight to `DEFAULT_BIAS`:

```python
    "travel": 3,
```

In `_pick_major`, restrict the choices before rolling:

```python
        gated = bool(state.get("_venue_gating"))
        here = state.get("_venue") or "plaza"
        available = set(actions_at(here, gated=gated))
        bias = {a: w for a, w in DEFAULT_BIAS.items() if a in available}
        choices: list[str] = []
        for action, weight in bias.items():
            choices.extend([action] * max(0, weight))
        action = rng.choice(choices) if choices else "travel"
```

The `fulfil_contract` shortcut above the roll must respect the gate too — add `and "fulfil_contract" in available` to its condition, so a gated stub does not short-circuit into an action the Market owns while standing elsewhere.

Generate `travel`'s argument in the same `if/elif` chain that builds the other actions' arguments:

```python
        if action == "travel":
            from app.oracle.world_data import BUILT_VENUES

            targets = [
                vid for vid, v in BUILT_VENUES.items() if vid != here and v.actions
            ]
            return AgentDecision(
                "travel",
                {"venue": rng.choice(sorted(targets))},
                monologue=f"({agent.display_name}) Walking somewhere useful.",
            )
```

Add `from app.oracle.world_data import actions_at` at the top of the module.

Filter the free-action pick in `decide` the same way. The existing block is a
`rng.random() < 0.4` gate around an `if free == ... elif ...` chain; narrow the
pool it chooses from and skip the chain entirely when the pool is empty:

```python
        if rng.random() < 0.4:
            others = [
                a
                for a in state["agents"]
                if a["agent_id"] != agent.agent_id and a["alive"]
            ]
            target = rng.choice(others)["agent_id"] if others else None
            available = set(
                actions_at(
                    state.get("_venue") or "plaza",
                    gated=bool(state.get("_venue_gating")),
                )
            )
            pool = [
                a
                for a in ("vouch", "bluff", "propose_deal", "slander")
                if a in available
            ]
            if pool:
                free = rng.choice(pool)
                ...  # the existing if/elif chain, unchanged
```

Leaving the chain untouched inside `if pool:` keeps this a two-line change and
keeps the ungated roll identical, which `test_an_ungated_stub_is_unchanged`
pins. Note that under gating the four free actions the stub knows about all live
at the Lounge, so a gated stub outside it takes no free action — correct, and
the reason the diversity test in Task 8 does not assert on free actions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_stub_gating.py tests/test_stub_agent.py -v`
Expected: PASS. If `tests/test_stub_agent.py` does not exist, run the whole suite instead: `python -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/stub.py backend/tests/test_stub_gating.py
git commit -m "feat(agents): a gated stub rolls only over what is here"
```

---

### Task 6: The API and runtime carry the flag

**Files:**
- Modify: `backend/app/main.py` (configure body, run endpoints)
- Modify: `backend/app/runtime.py` (per-session state)
- Test: `backend/tests/test_gating_config.py` (create)

**Interfaces:**
- Consumes: `run_events(..., venue_gating=...)` (Task 4).
- Produces: `POST /sessions/{id}/configure` accepts `"venue_gating": bool`, defaulting `False`; the session's value is readable at `GET /sessions/{id}/state` as `"venue_gating"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gating_config.py`:

```python
"""The gating flag is configured per session and reported in the snapshot."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


ROSTER = [
    {"agent_id": c, "display_name": c.title(), "provider": "stub", "personality": "x", "sprite": c}
    for c in ("red", "blue", "green")
]


async def test_gating_defaults_off():
    async with await _client() as client:
        sid = (await client.post("/sessions")).json()["session_id"]
        await client.post(f"/sessions/{sid}/configure", json={"agents": ROSTER})

        state = (await client.get(f"/sessions/{sid}/state")).json()

    assert state["venue_gating"] is False


async def test_gating_can_be_turned_on_at_configure_time():
    async with await _client() as client:
        sid = (await client.post("/sessions")).json()["session_id"]
        await client.post(
            f"/sessions/{sid}/configure",
            json={"agents": ROSTER, "venue_gating": True},
        )

        state = (await client.get(f"/sessions/{sid}/state")).json()

    assert state["venue_gating"] is True


async def test_a_non_boolean_flag_is_rejected():
    async with await _client() as client:
        sid = (await client.post("/sessions")).json()["session_id"]
        resp = await client.post(
            f"/sessions/{sid}/configure",
            json={"agents": ROSTER, "venue_gating": "yes please"},
        )

    # configure reports bad input as an `error` key on a 200, the same way
    # `condition` and `balance_visibility` already do. Do not invent a 400 here.
    assert "venue_gating" in resp.json()["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_gating_config.py -v`
Expected: FAIL — `KeyError: 'venue_gating'`

- [ ] **Step 3: Read, validate and store the flag**

In `backend/app/main.py`, in the configure handler beside the `condition` validation (around line 322):

```python
    venue_gating = body.get("venue_gating", False)
    if not isinstance(venue_gating, bool):
        return {
            "error": f"venue_gating must be a boolean, got {venue_gating!r}"
        }
```

This matches the two validations directly above it: `balance_visibility` and `condition` both return a bare `{"error": ...}` dict, not an `HTTPException` and not a status code.

Store it beside `sim.condition` (around line 395):

```python
        sim.venue_gating = venue_gating
```

Report it in the state payload beside `condition` (around line 239):

```python
        "venue_gating": bool(sim.venue_gating) if sim else False,
```

Pass it to the engine where `condition=sim.condition` is passed (around line 561):

```python
                    venue_gating=sim.venue_gating,
```

In `backend/app/runtime.py`, add the field to the per-session state object that already holds `condition`, defaulting to `False`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_gating_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/runtime.py backend/tests/test_gating_config.py
git commit -m "feat(api): venue_gating is a per-session setting"
```

---

### Task 7: The trace records the flag and replay obeys it

**Files:**
- Modify: `backend/app/trace/schema.py` (`RunManifest`)
- Modify: `backend/app/trace/recorder.py:128-155` (`_ensure_manifest` and its callers)
- Modify: whichever replay entry point reads `RunManifest` (`backend/app/trace/validate.py` or the replay CLI — grep for `RunManifest` and follow the readers)
- Test: `backend/tests/test_trace_gating_flag.py` (create)

**Interfaces:**
- Consumes: Tasks 4 and 6.
- Produces: `RunManifest.venue_gating: bool = False`; replay reads the flag from the manifest, never from settings.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_trace_gating_flag.py`:

```python
"""A trace says which rules it was recorded under, and replay believes it."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.trace.schema import RunManifest

BASE = {
    "kind": "run",
    "schema_version": 6,
    "run_id": "r1",
    "env": {},
    "horizon": 10,
    "agents": [],
}


def test_an_older_manifest_without_the_field_still_parses():
    manifest = RunManifest.model_validate(BASE)

    assert manifest.venue_gating is False


def test_the_flag_round_trips():
    manifest = RunManifest.model_validate({**BASE, "venue_gating": True})

    assert manifest.venue_gating is True
    assert manifest.model_dump(mode="json")["venue_gating"] is True


def test_a_non_boolean_flag_is_a_validation_error():
    with pytest.raises(ValidationError):
        RunManifest.model_validate({**BASE, "venue_gating": "maybe"})
```

If `EnvManifest` has required fields, fill `"env"` with the minimum they need rather than `{}` — run `python -c "from app.trace.schema import EnvManifest; print(EnvManifest.model_json_schema()['required'])"` from `backend/` to find out.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_trace_gating_flag.py -v`
Expected: FAIL — `AttributeError: 'RunManifest' object has no attribute 'venue_gating'`

- [ ] **Step 3: Add the field and thread it**

In `backend/app/trace/schema.py`, on `RunManifest` beside `state_fidelity`:

```python
    venue_gating: bool = False
```

Defaulting to `False` is what lets every trace recorded before this branch parse unchanged, which the first test pins.

In `backend/app/trace/recorder.py`, add `venue_gating: bool = False` to `_ensure_manifest`'s keyword-only parameters and to the two wrapper functions above it that already thread `condition` (lines 73 and 100), then include it in the manifest copy:

```python
    manifest = manifest.model_copy(
        update={
            "horizon": max(get_settings().max_turns, horizon),
            "venue_gating": venue_gating,
        }
    )
```

In `event_engine.run_events`, pass `venue_gating=venue_gating` wherever it calls `record_event`.

Then grep for every reader of `RunManifest` and make the replay path take gating from the manifest:

```bash
cd backend && grep -rn "RunManifest" app/ tests/ --include=*.py
```

Wherever a replay or probe constructs a run from a trace, pass `venue_gating=manifest.venue_gating` into `run_events` rather than a default or a settings lookup.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_trace_gating_flag.py tests/ -q`
Expected: PASS for the whole suite. The fidelity gate (`test_restored_world_brief_is_identical`, or whatever the current name is — grep for `fidelity`) is the one to watch: it fired when the registry landed and is the detector for a stimulus divergence here.

- [ ] **Step 5: Commit**

```bash
git add backend/app/trace/schema.py backend/app/trace/recorder.py backend/app/oracle/event_engine.py backend/tests/test_trace_gating_flag.py
git commit -m "feat(trace): a run records whether it was gated"
```

---

### Task 8: The diversity check, the ADR, and the docs

The spec names one risk above the others: gating may collapse behaviour, with agents settling into whichever building they woke in. This task builds the detector and writes down the decision.

**Files:**
- Create: `backend/tests/test_gating_diversity.py`
- Create: `docs/adr/2026-09-24-venue-gated-tools.md`
- Modify: `CLAUDE.md` (Game mechanics and Time sections)
- Modify: `docs/superpowers/specs/2026-09-13-venue-affordances-design.md` (status note)

**Interfaces:**
- Consumes: everything above.
- Produces: no code interfaces.

- [ ] **Step 1: Write the diversity test**

Create `backend/tests/test_gating_diversity.py`:

```python
"""Gating must not collapse the action distribution.

The failure mode this pack risks is an agent that never leaves the building it
woke in. A stub roster is the cheapest detector: it has no strategy, so any
narrowing is the mechanic's doing and not the model's.
"""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.stub import StubAgent
from app.db import Base
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.event_engine import run_events

SID = "div"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for aid in ("red", "blue", "green"):
            s.add(
                Agent(
                    session_id=SID,
                    agent_id=aid,
                    display_name=aid.title(),
                    provider="stub",
                    personality="x",
                    sprite=aid,
                    balance=10.0,
                    venue="plaza",
                )
            )
        await s.commit()
        yield s
    await engine.dispose()


async def test_a_gated_stub_run_visits_more_than_one_building(session):
    agents = {aid: StubAgent(agent_id=aid, model="stub") for aid in ("red", "blue", "green")}
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=60,
        seed=7, venue_gating=True,
    )

    rows = (
        await session.execute(
            select(ThoughtLog).where(ThoughtLog.session_id == SID)
        )
    ).scalars().all()
    actions = [r.action for r in rows]

    assert len(rows) > 10, "the run did not produce enough events to judge"
    # Travel exists so agents can reach other buildings; it must not be all they do.
    assert actions.count("travel") < len(actions) * 0.8
    assert len(set(actions)) >= 4
    assert sum("not available here" in (r.outcome or "") for r in rows) < len(rows) * 0.2
```

- [ ] **Step 2: Run it**

Run: `cd backend && python -m pytest tests/test_gating_diversity.py -v`
Expected: PASS. If it fails on the travel ratio, the dial is `DEFAULT_BIAS["travel"]` in `stub.py`; if it fails on the rejection ratio, the gate is leaking somewhere in Task 4 or 5 and that is a real bug, not a threshold to relax.

- [ ] **Step 3: Write the ADR**

Create `docs/adr/2026-09-24-venue-gated-tools.md`, following the shape of `docs/adr/2026-08-30-continuous-event-clock.md`:

- **Context.** Twenty-five actions in every prompt is affordable; forty-five is not. `2026-09-13-venue-affordances-design.md` decided any action stays callable from anywhere and the walk is the only gate, and solved prompt size by summarising other venues in one line each.
- **Decision.** Under `venue_gating`, a prompt offers only the current venue's actions plus `travel`, and `travel` is a major action. The ungated world stays available and unchanged as a comparison condition.
- **Consequences.** Location becomes a commitment: leaving the Market to reach the Alley is observable, so an alibi has teeth. Per-wake prompt cost stops growing with the world. Against that: an agent can now waste a wake being in the wrong place, traces from the two modes are not comparable, and the frozen-stimulus probes need a second baseline.
- **Reopen if.** Gated stub runs show a collapsed action distribution that `DEFAULT_BIAS` cannot fix, or the rejection rate in live runs stays above a few percent, which would mean the venue block is not conveying the situation.

- [ ] **Step 4: Update the docs that describe the old rule**

In `CLAUDE.md`, the **Game mechanics** section says:

> Any action is still callable from anywhere -- you pay the walk.

Replace that clause with the two-mode rule: ungated, any action is callable anywhere and the walk is charged automatically; under `venue_gating`, only the current building's actions plus `travel` are offered, and `travel` is a major action. Add `travel` to the action count (26 total, 12 major / 14 free) and mention the flag in the **Time** section beside `policy="lockstep"`, since both are run configuration that changes the stimulus.

In `docs/superpowers/specs/2026-09-13-venue-affordances-design.md`, add one line under the status header noting that Pack 0 of `2026-09-24-venue-content-packs-design.md` supersedes the "callable from anywhere" decision, and point at the ADR.

- [ ] **Step 5: Run the whole suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS, no skips that were not skipping before.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_gating_diversity.py docs/adr/2026-09-24-venue-gated-tools.md CLAUDE.md docs/superpowers/specs/2026-09-13-venue-affordances-design.md
git commit -m "docs(adr): venue-gated tools, and the diversity gate that watches them"
```

---

## Not in this plan

- Any new venue or action beyond `travel`. Packs 1-4 are separate specs and plans.
- Frontend changes. The renderer reads venues and positions from `shared/` and a walk from the trace; neither changes shape here.
- Re-baselining the frozen-stimulus probes under gating. That is a measurement task, and it needs a gated run worth baselining first.
- Turning gating on by default. The flag ships off; flipping it is a decision to make after the diversity numbers from Task 8 and a short live run.
