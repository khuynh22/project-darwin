# ADR 2: What writes a live session's trace to disk?

- **Status:** accepted
- **Date:** 2026-08-26
- **Deciders:** repository owner (product intent), tech-lead (decomposition)

## Context

A session run from the UI leaves nothing on disk. `TraceWriter` is called only from
`backend/app/cli/main.py:44` and `backend/app/sweep/cell.py:109`; the REST turn endpoints
(`/sessions/{id}/turn`, `/sessions/{id}/run`) write to Postgres and broadcast over the
WebSocket, and stop there. Replay reads only `releases/<run_id>/trace.jsonl`
(`backend/app/releases.py:57-70`), so a UI run is not replayable at all.

`export_session` (`backend/app/trace/adapters/darwin_db.py:31`) already turns a session's
DB rows into a manifest plus turn and world records. The question is when it runs, not how
the records are shaped.

The tension is durability against hot-path risk. `run_turn` is the only mutation path in
the system (`backend/app/oracle/engine.py:728-1020`); anything added inside it can block
the turn loop or fail a turn that would otherwise have committed.

## Constraints

- `TraceWriter` already flushes after every row and documents the reason: "a sweep that
  is killed mid-run must leave a truncated-but-parseable trace"
  (`backend/app/trace/io.py:14-27`).
- A turn is 3-10 agent records plus one world record. The largest existing run is 2,010
  lines for 335 turns; per-turn write volume is a few kilobytes.
- A turn's wall time is dominated by parallel model calls with a 120s timeout
  (`CLAUDE.md`, "Parallel execution"). A local file append is not measurable against that.
- Trace records must be built once, not twice: a second mapping alongside
  `export_session` reintroduces exactly the class of silent divergence that spec §1
  documents for `steal_count`.
- Sessions are multi-tenant and concurrent; `SessionRegistry` (`backend/app/runtime.py`)
  holds a per-session turn lock, so one writer per session has no contention with itself.

## Options

### A. Explicit publish endpoint

`POST /sessions/{id}/publish` calls `export_session` and writes `releases/<run_id>/`.
Nothing touches `run_turn`. Smallest change, zero hot-path risk. Costs: a crashed or
abandoned run leaves no artifact, and a run is not replayable while it is running — which
is most of the time a user is looking at it.

### B. Stream per turn from inside `run_turn`

After the turn commits, append this turn's records to `runs/<session_id>/trace.jsonl`.
A killed process leaves a truncated-but-parseable trace. Costs: a write on the mutation
path, and a per-turn record builder that must not diverge from `export_session`.

### C. Both

B for durability, plus A to promote a finished run into `releases/` with an `about.md`.

## Decision

**Option B, with the promotion half of C deferred.**

`run_turn` gains a per-turn trace append after `await session.commit()`
(`backend/app/oracle/engine.py:1020`), writing to `runs/<session_id>/trace.jsonl`. The
manifest line is written when the file is first opened for a session and rewritten on
promotion, not per turn.

Three rules make the hot-path write safe:

1. **Commit first, write second.** The DB is the source of truth (`CLAUDE.md`,
   multi-tenancy). A trace append can never fail a turn that has already committed; a
   write error is logged and the turn still returns.
2. **One record builder.** The per-turn builder is extracted from `export_session` and
   called by both, so the streamed trace and an exported trace are the same records by
   construction. `export_session`'s own tests continue to pass unchanged, which is what
   proves the extraction was faithful.
3. **`runs/` is not `releases/`.** A streamed trace is a working artifact, gitignored
   alongside the existing release artifacts. Promotion into `releases/` — which is what
   makes something citable and pairs it with `verdicts.jsonl`, `scores.json` and
   `about.md` — stays a separate, explicit act and is not in this plan.

## Rejected

Option A's strongest argument is that the mutation path in this system is uniquely
load-bearing: it is the only place the world changes, it is already the longest function
in the backend at ~290 lines, and every defect in it is a data defect rather than a
display defect. Keeping it untouched is genuinely the safer engineering instinct. It was
rejected because "replayable on the frontend" is the requirement, and a run that only
becomes replayable after someone remembers to press a button is not replayable — the
common case is a run that is still going, or one that died.

## Consequences

- **Becomes easy:** any UI run is replayable while it runs and after it crashes; the
  gallery replay and the live view read the same file format; sessions become
  self-describing artifacts without operator action.
- **Becomes hard:** disk fills with abandoned sessions — `runs/` has no retention policy
  and this plan does not add one. `session_id` now names a directory, so it is a path
  component and must be validated as one before it reaches the filesystem.
- **Becomes expensive to reverse:** little. The writer is one call site behind one
  setting; removing it leaves stale files but breaks no schema.

## Revisit when

`runs/` growth is observed to matter on the deployment target, or a second process needs
to write the same session's trace — the single-process assumption behind `SessionRegistry`
is what makes one open file handle per session safe, and it fails the moment the Oracle
runs more than one worker.
