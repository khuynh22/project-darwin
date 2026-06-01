# Multi-Tenant Sessions — Design

**Status:** Approved 2026-06-01
**Goal:** Let Project Darwin be launched as a public website where each visitor runs their own
isolated simulation. Today the Oracle holds one global game state shared by every connection.

## Decisions (locked)

| Question | Decision |
|---|---|
| Tenancy model | **Anonymous shareable sessions** — each sim gets a short URL slug (`/session/{id}`). No login. |
| API keys | **Per-session BYOK** — creator supplies keys, encrypted at rest, scoped to that session only. |
| Lifecycle | **Persist forever** — no TTL/cleanup job. |
| Runtime | **Single backend process** — in-memory per-session locks + registry; Postgres stores all data. |
| Naming | The tenant is a **"session"** (`session_id`), matching the codebase's existing `session_*.jsonl` vocabulary. |

**Out of scope (YAGNI):** auth/accounts, TTL/cleanup, rate limits, horizontal-scale coordination.

## Known limitation (accepted, documented not built)

Persist-forever + anonymous + single process ⇒ many sessions can run turn loops concurrently;
the real ceiling is the Postgres/SQLAlchemy **connection pool**, not CPU. No quotas built per the
lifecycle decision.

## Migration note (one-time)

Changing `Agent`'s primary key to `(session_id, agent_id)` is **destructive** — the additive
column backfill in `init_db()` cannot ALTER a primary key. **Deploying this requires a one-time DB
reset** (drop & recreate). Acceptable: pre-production.

---

## 1. Data model

- **New `sessions` table** (`models/session.py`, class `SimSession`):
  `session_id` (str slug, PK) · `current_turn` (int, replaces `_current_turn` global) ·
  `balance_visibility` (str) · `status` (`configuring`|`ready`) · `created_at`.
- **Add `session_id`** (String(32), indexed) to: `agents`, `transactions`, `thoughts`,
  `world_events`, `deferred_actions`.
- **`Agent` PK → composite `(session_id, agent_id)`.** All bare-string references
  (`spouse_id`, `allies`, `will_target`, `actor_id`/`target_id`) are **unchanged** — they only
  resolve *within* a session, so scoped lookups suffice.
- **Add `Agent.model`** (String(64), default "") so the provider model survives a lazy reload
  after restart (today it's lost on restart).
- **API keys → per-`(session_id, provider)`**, encrypted with existing Fernet code
  (`api_key.py`). The global `/api-keys` pool + endpoints are removed; keys arrive inline with
  `configure`.

## 2. Scoping enforcement (anti-leak — the highest-risk component)

A missed `.where(session_id==...)` = cross-session data leak. Funnel everything through:

- `actions._get_agent(session, session_id, agent_id)` — single read path for all 20 handlers.
- `actions._record(session, *, session_id, ...)` — stamps `session_id` on every Transaction.
- `engine._get_agent_by_id(session, session_id, agent_id)` — heir/target resolver
  (inheritance from `spouse_id`/`will_target` **must** be scoped).

**Completeness checklist** — every `select(`/`session.add(` site below gets `session_id` or is
justified:
- `actions.py`: `_get_agent`, `_record`, `do_charity` poorest-agent query, inline `WorldEvent(...)`
  (marriage, divorce, propose_deal, slander, vouch, bluff, gaslight) and `DeferredAction(...)`
  (invest, lend).
- `engine.py`: `seed_roster`, `_get_agent_by_id`, `_world_state`, `_agent_history`,
  `_apply_decision`, `_apply_survival_tax`, `_eliminate_agent`, `_check_bankruptcies`,
  `_process_deferred` (deferred maturity, agent lookups, extortion query, "paid" tx query),
  `run_turn` (db_agents, gaslight events, refreshed apex) + every `ThoughtLog`/`WorldEvent`/
  `Transaction` construction.

## 3. Runtime state (`app/runtime.py` — replaces module globals)

```
SessionRuntime = { session_id, lock: asyncio.Lock, roster (decrypted keys, in-memory only), balance_visibility }
SessionRegistry.get_or_load(session_id) -> reconstruct from DB on first hit (lazy), None if missing
```
- `_turn_lock` → per-session `SessionRuntime.lock` (different sessions run concurrently; turns
  within a session stay serial).
- `_current_turn` → `SimSession.current_turn` (DB is truth).
- `_active_roster` → `SessionRuntime.roster`.
- **Lifespan**: drop today's eager single-session restore; load lazily per session on first hit
  (`get_or_load` double-checks under a lock to handle the concurrent-first-hit race).

## 4. API + WebSocket surface

- `POST /sessions` → create, returns `{session_id}`.
- `POST /sessions/{id}/configure` · `/run?turns=N` · `/turn` · `GET /state` · `/ledger` ·
  `/events` · `/export/thoughts` · `POST /agents/{aid}/remove` · `/simulation/resume` · `/reset`.
- `GET /providers` stays global. `/health` stays.
- **`WS /ws/{session_id}`** — Broadcaster becomes room-aware (`dict[session_id, set[ws]]`);
  events fan out only to that session's room.
- **Critical fix:** `configure` and `reset` STOP calling `drop_all`/`create_all` (which nuke every
  session today) → scoped `DELETE ... WHERE session_id = :id`. Re-configuring deletes only its own
  rows then re-seeds.

## 5. Thought export

Replace the global `_active_exporter` file handle with an on-demand DB query:
`GET /sessions/{id}/export/thoughts` streams JSONL from `thoughts` for that session. (CLI script
keeps its own file exporter.)

## 6. CLI (`scripts/run_simulation.py`)

Uses a fixed `CLI_SESSION_ID = "cli"`; seeds + runs turns under it. No web registry involved.

## 7. Frontend

- New landing `app/page.tsx`: "New simulation" → `POST /sessions` → `router.push('/session/{id}')`.
- Move current page body to `app/session/[sessionId]/page.tsx`; thread `sessionId` into every fetch
  (`/sessions/{id}/...`) and `connectOracle(sessionId, ...)`. Add "copy share link".
- `lib/ws.ts`: `connectOracle(sessionId, ...)` targets `/ws/{id}` + `/sessions/{id}/state`; add
  `createSession()`.
- `ConfigPanel`: takes `sessionId`, posts to `/sessions/{id}/configure`, sends inline per-provider
  keys (`keys: {provider: rawKey}`); drop the global `/api-keys` save/list flow.

## 8. Tests

- Update `test_actions.py` / `test_engine_bankruptcy.py`: add `session_id` to Agent fixtures and
  handler/`_check_bankruptcies` calls.
- New `test_multitenant.py`: two sessions share `agent_id="red"`; an action in session A never
  reads/writes session B's row; `configure`/`reset` on A leaves B intact.
