# Phase 1: Freeze and Instrument — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture every piece of state that affects an outcome or the world brief, prove a restored world is indistinguishable from the original, and make a recorded frontier run re-executable offline with no API key.

**Architecture:** Three moves. `turn_snapshots` and `TurnState` gain the full agent state; the trace gains a `world` record kind and becomes v5; a content-addressed response cache lets a `CachedAgent` replay recorded model outputs through the real engine. No new mechanics — this phase freezes and instruments what exists.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy 2 async, pytest (`asyncio_mode = "auto"`), ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-08-24-layered-economy-and-replay-design.md` (Phase 1, §4 and §5)

**Status:** COMPLETE (2026-08-25). All five tasks landed; 274 backend tests pass, ruff clean. Environment tagged `darwin-1.0`. See `## Execution notes`.

## Global Constraints

- Trace schema becomes **v5**. v4 files still read and are reported `state_fidelity: partial`.
- Every new `turn_snapshots` column needs a matching row in `app/db.py::_MIGRATIONS`. Omitting one is silent — existing databases never gain the column. This has bitten twice.
- The restore-fidelity test must assert over **all** `Agent` columns discovered by reflection, not a hand-listed subset. A hand-listed subset is how the next mechanic reintroduces the `steal_count` defect.
- `session_id` is `varchar(32)`; money `round(x, 2)`; goods integers; all DB calls async.
- Tests run offline: `provider="stub"`, `StubJudge`, no `OPENROUTER_API_KEY`.
- `office`, `tier`, `capacity` are reserved: present in the schema, `null`/empty until their layer ships.

---

### Task 1: Complete per-turn agent state

**Files:**
- Modify: `backend/app/models/ledger.py` (`TurnSnapshot`)
- Modify: `backend/app/db.py` (`_MIGRATIONS`)
- Modify: `backend/app/oracle/engine.py` (snapshot write site)
- Test: `backend/tests/test_turn_snapshot_state.py` (extend)

**Interfaces:**
- Produces: `TurnSnapshot` columns `steal_count`, `allies`, `enemies`, `skip_next_turn`, `rest_bonus`, `will_target`, `share_balance`, `extortion_pending`, `bribe_pending`, `marriage_pending`.

**Why each:** `steal_count` drives `actions.py:474` steal success. `allies` and `share_balance` drive balance visibility in `render_world_brief`. `skip_next_turn` and `rest_bonus` change the next turn's outcome. The rest are social state the brief or handlers read.

- [x] **Step 1: Write the failing test**

```python
# append to backend/tests/test_turn_snapshot_state.py
async def test_snapshot_captures_every_mechanically_relevant_field():
    """A field absent here is a field a restored probe silently fabricates."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, "capture", _roster(), seed=7)
        agents = build_agents(roster=_roster())
        for turn in range(1, 6):
            await run_turn(session, session_id="capture", turn=turn, agents=agents, seed=7)
        rows = (await session.execute(
            select(TurnSnapshot).where(TurnSnapshot.session_id == "capture")
        )).scalars().all()
    await engine.dispose()

    required = {
        "balance", "trust_score", "alive", "inventory", "spouse_id",
        "steal_count", "allies", "enemies", "skip_next_turn", "rest_bonus",
        "will_target", "share_balance", "extortion_pending", "bribe_pending",
        "marriage_pending",
    }
    missing = required - set(TurnSnapshot.__table__.columns.keys())
    assert not missing, f"turn_snapshots is missing {sorted(missing)}"
    assert rows
    assert all(isinstance(r.allies, list) for r in rows)
    assert all(isinstance(r.steal_count, int) for r in rows)


def test_every_new_snapshot_column_has_a_migration_row():
    """Adding a column without a _MIGRATIONS row leaves existing databases behind."""
    import inspect

    from app import db as db_mod
    from app.models.ledger import TurnSnapshot

    source = inspect.getsource(db_mod.init_db)
    for column in TurnSnapshot.__table__.columns.keys():
        if column in {"id", "session_id", "turn", "agent_id", "created_at"}:
            continue
        assert f'"turn_snapshots", "{column}"' in source, (
            f"turn_snapshots.{column} has no _MIGRATIONS row"
        )
```

- [x] **Step 2: Run to verify it fails**

`cd backend && python -m pytest tests/test_turn_snapshot_state.py -v`
Expected: FAIL — missing columns.

- [x] **Step 3: Implement**

Add to `TurnSnapshot` after `spouse_id`, matching `Agent`'s column types:

```python
    steal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    enemies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skip_next_turn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rest_bonus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    share_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    will_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marriage_pending: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extortion_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bribe_pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Add the matching `_MIGRATIONS` rows in `app/db.py` (types: `INTEGER`, `JSON`, `BOOLEAN`, `VARCHAR(64)`), then populate all of them at the `TurnSnapshot(...)` write site in `engine.py`.

- [x] **Step 4: Run to verify it passes** — plus `tests/test_seed_reproducibility.py` to confirm RNG draw order is undisturbed.

- [x] **Step 5: Commit** — `feat(engine): capture complete agent state per turn`

---

### Task 2: Trace v5 — full state and world records

**Files:**
- Modify: `backend/app/trace/schema.py`
- Modify: `backend/app/trace/validate.py`, `backend/app/trace/io.py`
- Modify: `backend/app/trace/adapters/darwin_db.py`
- Test: `backend/tests/test_trace_schema.py`, `backend/tests/test_trace_v5.py` (new)

**Interfaces:**
- Produces: `TRACE_SCHEMA_VERSION = 5`; `TurnState` gains the Task 1 fields plus `deferred`, `office`, `tier`, `capacity`; new `WorldRecord` (`kind: "world"`) with `contracts`, `offices`, `prices`, `info_market`; `parse_record` discriminates three kinds.

**Compatibility rule:** `RunManifest.schema_version` accepts `4` or `5`. A v4 file loads and reports `state_fidelity: partial`; a v5 file with complete state reports `full`. Readers that ignore `world` records still see a valid turn stream.

- [x] **Step 1: Write the failing test** — pin: version is 5; a v4 manifest still parses; a `world` record round-trips; `read_trace` returns world records separately from turns without disturbing turn order; `validate_trace` rejects a world record whose turn exceeds the horizon; `TurnState` carries `steal_count` and `allies`; `export_session` populates them from `turn_snapshots` and emits one world record per turn.

- [x] **Step 2–5:** standard cycle. Commit as `feat(trace): schema v5 with complete state and world records`.

---

### Task 3: Restore fidelity — the gate

**Files:**
- Modify: `backend/app/probe/replay.py` (`restore_world`)
- Test: `backend/tests/test_restore_fidelity.py` (new)

**Interfaces:**
- `restore_world` restores every field in `TurnState`, not the current five.

**Why this is the gate:** matching database columns proves the engine agrees. Matching `render_world_brief` output proves **the model sees the same world**, which is what a probe actually depends on. Only the second one catches an `allies` omission.

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_restore_fidelity.py
"""Restoring a frozen turn must be indistinguishable from having lived it."""

RESTORE_EXEMPT = {
    # Identity and bookkeeping, not world state.
    "session_id", "agent_id", "display_name", "provider", "model", "personality",
    "sprite", "created_at", "consecutive_errors", "last_error", "eliminated_at_turn",
}


async def test_restored_world_matches_every_agent_column(...):
    # run N turns, export at turn N, restore into a fresh session,
    # then for every Agent column not in RESTORE_EXEMPT assert equality.
    ...


async def test_restored_world_brief_is_identical(...):
    """The model must see the same world, not merely an equivalent database."""
    # for each agent: render_world_brief(original_state, aid) == render_world_brief(restored_state, aid)
    ...


async def test_a_new_agent_column_fails_until_handled():
    """Reflection, not a hand-listed subset -- that is how steal_count was missed."""
    from app.models.agent import Agent
    from app.trace.schema import TurnState

    covered = set(TurnState.model_fields) | RESTORE_EXEMPT | {"agent_id"}
    uncovered = set(Agent.__table__.columns.keys()) - covered
    assert not uncovered, (
        f"Agent columns not carried by TurnState and not exempt: {sorted(uncovered)}. "
        "Add them to TurnState or to RESTORE_EXEMPT with a reason."
    )
```

- [x] **Step 2–5:** standard cycle. Commit as `test(probe): restore fidelity gate over all agent state`.

---

### Task 4: Response cache and CachedAgent

**Files:**
- Create: `backend/app/replay/__init__.py`, `backend/app/replay/cache.py`, `backend/app/replay/cached_agent.py`
- Test: `backend/tests/test_response_cache.py` (new)

**Interfaces:**
- `ResponseCache(root: Path)` with `key(...) -> str`, `get(key) -> dict | None`, `put(key, value)`, `stats()`.
- `CachedAgent(inner: BaseAgent | None, cache: ResponseCache, *, mode: "strict" | "permissive", env_version: str)`.
- `CacheMiss(Exception)`.

**Deliberate deviation from the spec:** the spec says the cache stores the raw provider response. This stores the **`AgentDecision`** instead — what the engine actually consumes. It is simpler, avoids coupling to the OpenAI response shape, and freezes the decision as published rather than letting a later parser change re-derive it. Recorded here because it is a real trade-off: a parser fix will not retroactively change a cached run, which is the desired behaviour for reproducing published numbers.

**Key:** `sha256(env_version, model, prompt_version, system_prompt, user_prompt, tool_names, temperature)`. The rendered prompts are included because they encode the world state — that is what makes the key correct rather than a proxy.

- [x] **Step 1: Write the failing test** — pin: a key is stable across processes (`PYTHONHASHSEED` varied, as `replay._session_id` needed); differing world state yields a different key; `strict` mode raises `CacheMiss` rather than calling the inner agent; `permissive` falls through and records; a recorded decision replays identically; an `env_version` mismatch raises rather than silently serving a stale entry.

- [x] **Step 2–5:** standard cycle. Commit as `feat(replay): content-addressed response cache and CachedAgent`.

---

### Task 5: `darwin replay --from-cache` and the version tag

**Files:**
- Modify: `backend/app/cli/main.py`
- Create: `backend/app/replay/reexecute.py`
- Test: `backend/tests/test_cli_reexecute.py` (new)

**Interfaces:**
- `async def reexecute(trace_path, cache_root, session_factory, *, mode) -> ReexecuteReport` with `turns`, `cache_hits`, `cache_misses`, `divergences`.
- CLI: `darwin replay <trace> --from-cache <dir> [--mode strict|permissive]`.

**What it proves:** re-running a recorded trace through the *real engine* with cached model outputs reproduces the recorded turns. A divergence is a genuine finding — either the environment changed or the cache is stale — and must be reported per turn, never summarised away.

- [x] **Step 1: Write the failing test** — pin: a stub run recorded to cache re-executes with zero misses in `strict` mode and zero divergences; deleting one cache entry makes `strict` fail loudly rather than falling back; a mismatched `env_version` refuses to run.

- [x] **Step 2–5:** standard cycle. Commit as `feat(cli): offline re-execution from a response cache`.

- [x] **Step 6: Tag the environment version.** Set `env.version` from a constant (`app/config.py::ENV_VERSION = "darwin-1.0"`), stamp it into the trace manifest, and document in the spec that any mechanic change bumps it and invalidates every cache.

---

## What this plan does not cover

Phases 2–6 of the spec: contracts and institutions, production chains, information markets, social strata, and the 3-D view. Each is its own plan. None may start before Task 3's fidelity gate is green, because every later phase adds state that the gate is what protects.


## Execution notes

**1. The fidelity gate was verified by breaking it, not by trusting it.** A gate that passes vacuously is worse than none, because it converts an unchecked assumption into a false guarantee. Two regressions were injected and reverted: dropping `allies` from the restore fails both the column check and the world-brief check; dropping `steal_count` fails three tests including its own. The world-brief half is the one doing real work — `_world_state` feeds both fields into what the model is shown, so an incomplete restore changes the *stimulus*, not merely the engine's arithmetic.

**2. The engine swallows agent exceptions, which quietly defeated strict mode.** `engine.py` logs and falls back when `decide()` raises, so one provider outage cannot kill a live turn. Right there, wrong for replay: a `CacheMiss` was absorbed and the run finished as a different experiment wearing the same name — precisely the failure the mode exists to prevent. Misses are now counted independently and any non-zero count fails the report. Note the subtlety this forces: the engine's fallback action can coincide with the recorded one, so *absence of divergence does not prove the cache served the run*. `ok` requires zero misses on its own evidence.

**3. A stale session poisoned the CLI path.** `seed_roster` skips agents that already exist, so leftover rows from an earlier attempt started the re-execution mid-game and every later turn diverged for the wrong reason. `reexecute` now purges the target session first. This only surfaced through the CLI test, because the unit tests each built a fresh in-memory database — worth remembering that the persistent path has failure modes the isolated one cannot show.

**4. Env version is pre-flighted, not discovered.** Checking one cache entry up front beats finding the mismatch turn by turn, especially given (2): the run would otherwise complete against the wrong environment before anyone noticed.

**5. Deviation from the spec, deliberate.** The spec says the cache stores the raw provider response; it stores the `AgentDecision`. Simpler, avoids coupling to the OpenAI response shape, and freezes the decision *as published* — a later parser fix will not retroactively change a cached run, which is the behaviour wanted for reproducing paper numbers.

## Verified

```
274 backend tests pass, ruff clean
darwin replay <trace> --from-cache <dir>
  -> N turns re-executed, N cache hits, 0 misses, 0 divergences
the released 2009-turn v4 trace still validates after the v5 bump
```

## What Phase 1 leaves for Phase 2

Nothing blocking. The gate is green, so contracts and institutions can start — and every field that layer adds to agent state will fail `test_a_new_agent_column_fails_until_handled` until it is carried by `TurnState` or exempted with a reason.
