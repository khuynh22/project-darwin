# Plan: 3-D as the only world view, with every UI run traced to disk and replayable

**Date:** 2026-08-26
**Owner:** tech-lead
**Requirements source:** `docs/superpowers/specs/2026-08-24-layered-economy-and-replay-design.md`
§5-§6 (approved, with acceptance criteria), amended by:

- `docs/adr/2026-08-26-3d-primary-renderer.md` — 3-D replaces 2-D everywhere; §6's
  "never a replacement" and 2-D fallback clauses are superseded.
- `docs/adr/2026-08-26-live-session-trace-on-disk.md` — `run_turn` streams a trace per
  turn to `runs/<session_id>/trace.jsonl`.

## Conventions found, and where this plan sits inside them

| Convention | Where | This plan |
|---|---|---|
| Oracle authoritative, frontend is a pure viewer | `CLAUDE.md`; spec §2 | Held. The 3-D scene consumes a view-model and computes nothing. |
| 3-D is a playback renderer with no game logic | spec §6; `frontend/CLAUDE.md` | Held, and extended to the live view — still playback, now over a live snapshot. |
| Trace records are built in one place | `backend/app/trace/adapters/darwin_db.py:31` | Held by extraction, not by a second builder (ADR 2, rule 2). |
| `TraceWriter` flushes per row so a killed run stays parseable | `backend/app/trace/io.py:14-27` | Reused as-is. |
| Money `round(x, 2)`, goods integers, all DB calls async | `CLAUDE.md` | Untouched — no mechanic changes here. |
| Agent identity is colour, never a sprite name | `frontend/CLAUDE.md` | Held; `AgentSnap.sprite` stays a colour key into `COLOR_HEX`. |
| Frontend CI is lint + typecheck + build only | `.github/workflows/ci.yml` | **Deviation:** this plan adds a unit runner (F0) and one browser gate (F8). Without them every frontend definition of done is "it compiles", and the ADR's blocking acceptance criterion has no gate at all. |
| Docs live in `docs/superpowers/specs`, `docs/research` | `docs/` | **Deviation:** ADRs go in a new `docs/adr/`. Specs describe designs; these record decisions that overrule one. |
| Release artifacts are gitignored per-file | `.gitignore:50-53` | `runs/` follows the same shape. |

## Sequence rationale

**S1 goes first because it can void the plan.** ADR 1 deletes the 2-D stage on the premise
that a 3-D scene can present the triple — private reasoning, public message, applied
action, verdict — at the readability of `frontend/components/TurnCard.tsx`. Spec §6 names
that as the acceptance criterion and calls burying the triple "a regression, not a
feature". If it cannot be done, ADR 1 is wrong, `Town.tsx` must stay, and F5-F8 change
shape. Answering it costs a throwaway prototype and a browser; discovering it at F5 costs
the plan.

**The backend chain (B1-B3) is second because its failure mode is silent.** A per-turn
record builder that drifts from `export_session` produces traces that parse, replay, and
are wrong — the same class of defect spec §1 documents for `steal_count`. It is also the
half that must be right before any 3-D work is worth watching: without it a live run has
nothing on disk to replay.

Frontend rendering (F2-F7) is last because every one of its failures is visible
immediately. The deletion of `Town.tsx` (F6) is deliberately second-to-last: it is the
only irreversible step, and it stays reversible-by-not-doing-it until the replacement is
gated by F8.

## Parallelisable

- **After S1:** the backend chain (B1 → B2 → B3) and the frontend chain (F0 → F1 → F2)
  share no files and can run at once.
- **F0 is independent of everything** and can start immediately; it is not first only
  because it removes no risk.
- **Must not run in parallel:** F2, F3, F5 and F7 all edit
  `frontend/components/three/WorldScene.tsx`. F1 and F6 both touch `frontend/lib/` and
  `frontend/components/` but different files; F6 rewrites `Critter.tsx`, which F2 must
  not.
- **D1 depends on everything** and must be last, or it documents a system that does not
  exist yet.

## Tasks

- [x] **S1 · Spike: can the triple stay legible inside the 3-D view?** — `senior-engineer`
  - Goal: a written answer to "where does the triple panel live — docked beside the canvas,
    or as an in-canvas HTML overlay — and does it read as well as `TurnCard` at 1280x800
    and at 390x844?", with a screenshot of each candidate.
  - Files in scope: throwaway branch only. Prototype over
    `frontend/app/gallery/[runId]/3d/page.tsx` against the released run
    `releases/leaderboard_335t_20260726`. No file is kept.
  - Pattern to follow: `frontend/components/TurnCard.tsx:22-45` is the readability bar —
    three tone-coded channel blocks plus a verdict row. Use the `browser-verification`
    skill; this is checked in a real browser, not in a test.
  - Definition of done: `cd frontend && npm run dev` serves
    `/gallery/leaderboard_335t_20260726/3d`, and the answer plus both screenshots are
    appended to this file under "S1 outcome".
  - Out of scope: agent pawns, animation, the live view, anything backend. A static scene
    with one hardcoded selected turn is enough to answer the question.
  - Stop condition: if neither layout reaches `TurnCard` readability at 390x844, stop and
    escalate — ADR 1 is void and the plan needs re-cutting, not a workaround.
  - Depends on: none.
  - Tier: **T2.** Two defensible layouts with different consequences for F3 and F5, and
    the outcome can overturn an accepted ADR. Above T1's "copy an existing pattern"
    ceiling; below T3 because the architecture is already decided — this only chooses
    where a panel sits.

- [x] **B1 · Extract a single-turn record builder from `export_session`** — `senior-engineer`
  - Goal: `export_session` produces identical output while a new public function builds
    the `TurnRecord`s and `WorldRecord` for exactly one turn.
  - Files in scope: `backend/app/trace/adapters/darwin_db.py`, `backend/app/trace/__init__.py`
    if an export is needed, new tests in `backend/tests/`.
  - Pattern to follow: `backend/app/trace/adapters/darwin_db.py:31-192` — the field mapping
    already exists; this moves it, it does not rewrite it.
  - Definition of done: `cd backend && python -m pytest tests/ -q`
  - Out of scope: changing any field mapping, the trace schema, or `TRACE_SCHEMA_VERSION`.
    If a field looks wrong, leave it wrong and say so — a mapping change here silently
    invalidates every existing trace comparison.
  - Stop condition: if a per-turn view cannot be built without re-querying the DB per turn,
    stop and escalate. That is a shape change to `export_session`'s contract, not a refactor.
  - Depends on: none.
  - Tier: **T2.** The existing tests are the only proof the extraction was faithful, and the
    caller contract (spec §4.1 completeness) is load-bearing for every restored probe.
    Contract-change trigger on the ladder.

- [x] **B2 · Stream a trace to disk from `run_turn`** — `senior-engineer`
  - Goal: running a session from the UI leaves a parseable `runs/<session_id>/trace.jsonl`
    that grows by one turn's records per turn, and a process killed mid-run leaves a
    truncated-but-parseable file.
  - Files in scope: `backend/app/oracle/engine.py` (append after the commit at line 1020),
    new `backend/app/trace/recorder.py`, `backend/app/config.py` (a `runs_dir` setting),
    `.gitignore`, new tests in `backend/tests/`.
  - Pattern to follow: `backend/app/sweep/cell.py:109` for the writer lifecycle;
    `backend/app/trace/io.py:14-27` for why per-row flushing is the durability guarantee.
  - Definition of done: `cd backend && python -m pytest tests/ -q`
  - Out of scope: promoting a run into `releases/`, retention or cleanup of `runs/`,
    `about.md`, verdicts. Do not move the write before the commit.
  - Stop condition: escalate if a write failure can propagate out of `run_turn` — a
    committed turn must never be failed by a logging concern (ADR 2, rule 1). Escalate
    rather than improvise if `session_id` reaches a path without validation: it is
    user-controlled, and this change makes it a directory name.
  - Depends on: B1.
  - Tier: **T2.** Touches the only mutation path in the system, and turns user-controlled
    input into a filesystem path — security-surface trigger on the ladder.

- [x] **B3 · Serve a live session's on-disk trace to the frontend** — `software-engineer`
  - Goal: `GET /sessions/{id}/trace/turns?offset=&limit=` returns the same shape as
    `GET /releases/{run_id}/turns`, read from `runs/<session_id>/trace.jsonl`.
  - Files in scope: `backend/app/main.py`, `backend/app/releases.py` (reuse the reader, do
    not fork it), new tests in `backend/tests/`.
  - Pattern to follow: `backend/app/main.py:108-121` — the release turns endpoint,
    including its `MAX_PAGE` clamp and 404 shape.
  - Definition of done: `cd backend && python -m pytest tests/ -q`
  - Out of scope: verdicts and scores for a live session — the judge runs offline and there
    are none. Do not invent an empty-verdict endpoint.
  - Stop condition: if serving the file requires holding a read lock against the live
    writer, stop and escalate; the answer is a read-only reopen, not coordination.
  - Depends on: B2.
  - Tier: **T1.** One endpoint copied from a demonstrated pattern two screens up in the
    same file, no interface anyone else depends on.

- [x] **F0 · Add a frontend unit-test runner** — `software-engineer`
  - Goal: `npm test` runs and passes in `frontend/`, and CI runs it.
  - Files in scope: `frontend/package.json`, a vitest config, one trivial test,
    `.github/workflows/ci.yml`.
  - Pattern to follow: the backend's shape — `pytest -q` as one command, wired into CI
    beside lint and typecheck (`.github/workflows/ci.yml`, backend job).
  - Definition of done: `cd frontend && npm test`
  - Out of scope: component or DOM testing, jsdom setup, snapshot tests. This runner exists
    for pure functions in `lib/`; F8 covers the rendered page.
  - Stop condition: if the runner needs a jsdom environment to start, stop — that means it
    is being pointed at components, which is out of scope.
  - Depends on: none.
  - Tier: **T1.** New tooling, but a well-trodden pattern with no interface impact.

- [x] **F1 · `lib/frame.ts`: one view-model from both sources** — `senior-engineer`
  - Goal: `buildFrameFromSnapshot(WorldSnapshot)` and `buildFramesFromTurns(ReleaseTurn[])`
    return the same `WorldFrame` type — per-agent venue, slot position, colour, action and
    the triple — so the renderer never sees which source it came from.
  - Files in scope: new `frontend/lib/frame.ts`, new `frontend/lib/frame.test.ts`.
    Read-only: `frontend/components/Town.tsx`, `frontend/lib/town.ts`,
    `frontend/lib/world3d.ts`, `frontend/lib/releases.ts`, `frontend/lib/ws.ts`.
  - Pattern to follow: `frontend/components/Town.tsx:37-70` — venue assignment, the
    spouse-follow rule and stable slot ordering are already written there; this moves that
    law out of the renderer, it does not redesign it. Slot geometry comes from
    `frontend/lib/world3d.ts:34` (`agentSlot`), not from `venueSlot`.
  - Definition of done: `cd frontend && npm test`
  - Out of scope: editing `Town.tsx` (F6 deletes it), rendering, animation. A live frame
    carries no verdict — the judge runs offline. Model that absence as `verdict: null`; do
    not fabricate one.
  - Stop condition: escalate if the two sources cannot produce one type without a
    discriminated union leaking into the renderer — that means ADR 1's single-renderer
    premise needs revisiting.
  - Depends on: F0. Not on S1 — the frame contract is unaffected by where the panel sits.
  - Tier: **T2.** Inventing the abstraction the whole plan rests on, out of logic currently
    fused to a component. The pattern must be created, not copied — above T1's ceiling.

- [x] **F2 · Render agents in the scene from a `WorldFrame`** — `software-engineer`
  - Goal: `/gallery/[runId]/3d` shows one pawn per living agent, at its action's venue, in
    its agent colour, for a given frame.
  - Files in scope: new `frontend/components/three/AgentPawn.tsx`,
    `frontend/components/three/WorldScene.tsx`, `frontend/app/gallery/[runId]/3d/page.tsx`.
  - Pattern to follow: `frontend/components/three/VenueBlock.tsx` — a positioned group of
    meshes plus a billboarded `Text` label, with positions taken from a helper rather than
    computed inline.
  - Definition of done: `cd frontend && npm run build`
  - Out of scope: selection, the triple panel, the scrubber, walk animation between venues,
    the live view. Dead agents are simply absent this task.
  - Stop condition: if pawns need per-frame state the `WorldFrame` does not carry, stop —
    extend F1's contract with its owner rather than reaching past it into the snapshot.
  - Depends on: F1.
  - Tier: **T1.** A new component built by copying `VenueBlock`'s demonstrated shape,
    consuming a contract someone else defined.

- [x] **F3 · Selection and the triple panel** — `software-engineer`
  - Goal: clicking a pawn shows that agent-turn's private reasoning, public message,
    applied action and verdict, in the layout S1 chose.
  - Files in scope: `frontend/components/three/WorldScene.tsx`,
    `frontend/components/three/AgentPawn.tsx`, new
    `frontend/components/three/TriplePanel.tsx`, `frontend/app/gallery/[runId]/3d/page.tsx`.
  - Pattern to follow: `frontend/components/TurnCard.tsx:22-45` — reuse its `Channel`
    block, tones and verdict presentation. This is the readability bar in spec §6, so copy
    it rather than restyling it.
  - Definition of done: `cd frontend && npm run build`
  - Out of scope: the scrubber, the live view, keyboard navigation between agents.
  - Stop condition: escalate if the panel cannot reuse `TurnCard`'s channel presentation —
    a second, divergent way of showing the triple is the regression spec §6 warns about.
  - Depends on: S1, F2.
  - Tier: **T1.** The hard question — where the panel sits and whether it reads — was
    answered by S1. What remains is wiring a click to a known component.

- [x] **F4 · Turn scrubber over a released run** — `software-engineer`
  - Goal: a turn slider and play/pause step the 3-D gallery view through the whole run, and
    the pawns and panel follow the cursor.
  - Files in scope: `frontend/app/gallery/[runId]/3d/page.tsx`, new
    `frontend/components/three/TurnScrubber.tsx`.
  - Pattern to follow: `frontend/app/gallery/[runId]/page.tsx:41-56` for paged fetching via
    `fetchTurns`, and the `AUTO_PLAY_DELAY_MS` cadence in
    `frontend/app/session/[sessionId]/page.tsx` for auto-advance.
  - Definition of done: `cd frontend && npm run build`
  - Out of scope: prefetching a 2,010-line trace in one request, branching, re-execution.
    Page as the 2-D view already does.
  - Stop condition: if smooth scrubbing needs the whole trace resident, stop and escalate
    rather than raising `MAX_PAGE` — that is a backend contract change.
  - Depends on: F3.
  - Tier: **T1.** Paging and an interval loop, both demonstrated elsewhere in this app.

- [x] **F5 · The live session view renders the 3-D scene** — `senior-engineer`
  - Goal: `/session/[sessionId]` shows the 3-D world driven by the live WebSocket snapshot,
    with Step / +10 / Auto / Config / Reset still working exactly as before.
  - Files in scope: `frontend/app/session/[sessionId]/page.tsx`,
    `frontend/components/three/WorldScene.tsx`.
  - Pattern to follow: the mount at `frontend/app/gallery/[runId]/3d/page.tsx:11-15` —
    `next/dynamic` with `ssr: false`, so three.js never enters the server bundle.
  - Definition of done: `cd frontend && npm run build`
  - Out of scope: deleting `Town.tsx` (F6), the no-WebGL notice (F7), the sidebar, the logs
    and `ConfigPanel` — all unchanged. Do not add a scrubber to the live view; it follows
    the head of the run.
  - Stop condition: escalate if the live snapshot cannot place every living agent. `_state`
    returns only the newest 20 `ThoughtLog` rows (`backend/app/main.py:186-193`), which with
    10 agents is two turns of history. If an agent cannot be placed, the fix is a backend
    field, not a frontend guess.
  - Depends on: F2, F3. Not on F4.
  - Tier: **T2.** Replaces the primary view of the application and changes what a running
    session looks like; blast radius exceeds the component being edited.

- [x] **F6 · Delete the 2-D stage, keep `CritterAvatar`** — `software-engineer`
  - Goal: `frontend/components/Town.tsx` is gone, `Critter.tsx`'s stage rendering is gone,
    and the roster and config modal still show their avatar heads.
  - Files in scope: delete `frontend/components/Town.tsx`; move `CritterAvatar` out of
    `frontend/components/Critter.tsx` into a new `frontend/components/Avatar.tsx` and delete
    the rest; update imports at `frontend/components/Sidebar.tsx:5`,
    `frontend/components/ConfigPanel.tsx:17`, `frontend/app/session/[sessionId]/page.tsx:23`.
    Remove the now-dead stage keyframes from `frontend/app/globals.css`.
  - Pattern to follow: `frontend/components/Critter.tsx:230` — `CritterAvatar` is already a
    self-contained export and moves whole.
  - Definition of done: `cd frontend && npm run build`
  - Out of scope: `frontend/lib/town.ts` — `VENUES`, `ACTIONS`, `COLOR_HEX` and
    `HOME_VENUES` are still the source of truth for the 3-D view and must not be touched.
    `venueSlot` may become unused; leave it.
  - Stop condition: stop if anything other than the avatar still imports `Critter.tsx` after
    F5 — something was not migrated, and deleting is the wrong answer.
  - Depends on: F5, F8. This is the irreversible step; it runs only after the replacement is
    gated.
  - Tier: **T1.** Five files, so above T0's two-file ceiling, but every edit is named here
    and no judgement is required.

- [x] **F7 · Honest capability notice when WebGL is unavailable** — `intern-engineer`
  - Goal: with WebGL unavailable, both `/session/[sessionId]` and `/gallery/[runId]/3d` show
    a notice explaining that the world needs WebGL, linking to the run's raw trace and the
    thoughts export — never a blank canvas.
  - Files in scope: `frontend/app/session/[sessionId]/page.tsx`,
    `frontend/app/gallery/[runId]/3d/page.tsx`.
  - Pattern to follow: `frontend/app/gallery/[runId]/3d/page.tsx:63-82` — the existing
    `webgl === false` block. Copy its card exactly; replace the link to the 2-D view, which
    no longer exists, with the export links.
  - Definition of done: `cd frontend && npm run build`
  - Out of scope: any fallback renderer, a static image, `hasWebGL()` itself
    (`frontend/lib/world3d.ts:52` is correct and stays).
  - Stop condition: the brief names both files and the block to copy. Anything beyond that —
    a different message per route, a raster fallback — is an escalation.
  - Depends on: F5.
  - Tier: **T0.** Two files, one copied block, no schema, no interface, no judgement.

- [x] **F8 · Browser gate for the triple** — `test-engineer`
  - Goal: an automated check loads `/gallery/[runId]/3d`, selects an agent-turn, and asserts
    the private reasoning, public message, applied action and verdict are all present and
    visible.
  - Files in scope: new `frontend/e2e/triple.spec.ts`, `frontend/package.json`,
    `.github/workflows/ci.yml`.
  - Pattern to follow: `playwright` is already a root dependency (`package.json`); run
    against `npm run build && npm start`, with the checked-in release
    `releases/leaderboard_335t_20260726` as the fixture.
  - Definition of done: `cd frontend && npm run test:e2e`
  - Out of scope: visual regression, cross-browser, the live session view (it needs a running
    Oracle and an API key), performance.
  - Stop condition: escalate if the gate cannot run headless in CI — a check only a human
    runs is not a gate, and F6 depends on this one being real.
  - Depends on: F3.
  - Tier: **T1.** This is the gate on the ADR's blocking criterion and the only thing
    standing between F6 and an unverified deletion. Assigned to `test-engineer` rather than
    `software-engineer` for that reason.

- [x] **D1 · Documentation catches up with the decisions** — `docs-engineer`
  - Goal: a reader who opens the repo after this lands is not told the frontend has a 2-D
    town, or that the 3-D view is gallery-only.
  - Files in scope: `frontend/CLAUDE.md`, `CLAUDE.md` (repo layout block),
    `docs/HOW-TO-RUN.md` (how to find and replay a UI run's trace),
    `docs/superpowers/specs/2026-08-24-layered-economy-and-replay-design.md` (a supersession
    note on §6 pointing at ADR 1 — amend, do not rewrite the spec).
  - Pattern to follow: `frontend/CLAUDE.md` "Where things live" — one line per file, naming
    what it owns.
  - Definition of done: `grep -rn "Town.tsx\|Critter.tsx" CLAUDE.md frontend/CLAUDE.md docs/`
    returns only historical references inside `docs/adr/`.
  - Out of scope: the paper, `docs/research/`, `releases/README.md`.
  - Stop condition: if the spec needs more than a supersession note, stop — rewriting an
    approved spec is a decision, not documentation.
  - Depends on: F6, F7.
  - Tier: **T1.** Mechanical against a settled system, but it spans four files and must
    describe the decisions accurately.

## Corrections found while executing

Four things the plan got wrong, recorded rather than quietly worked around.

- **S1's definition of done named `npm run dev`.** The 3-D scene does not render there:
  `reactStrictMode` double-mounts the R3F canvas and the GL context is lost. Every visual
  check ran against `npm run build && npm start` instead. Pre-existing on `main`, not
  introduced here, and not fixed here.
- **F2's file list omitted `lib/world3d.ts`.** Agent slots at the old radius fell inside
  the venue footprint, so pawns were drawn behind the plinth — F2's own goal, "shows one
  pawn per living agent", was not observably met without widening it. `VENUE_FOOTPRINT`
  moved to `lib/world3d.ts` so the clearance is asserted rather than assumed.
- **F3 needed `TurnCard.tsx`.** S1 required reusing `Channel` rather than restyling it,
  and `Channel` was private to `TurnCard`. Extracted to `components/Triple.tsx`, along
  with the verdict row, in a separate structural commit.
- **F7's premise and F8's fixture were both wrong.** F7 assumed the 2-D view no longer
  existed; only the 2-D *town stage* was deleted, and `/gallery/[runId]` still shows the
  same run with verdicts — so the gallery notice was left as written and only the session
  view gained one. F8's fixture was to be the checked-in release, but `releases/*/trace.jsonl`
  is gitignored and CI has no copy; the gate stubs the Oracle with an inline fixture instead.

## Noticed, not touched

- The dev-mode WebGL context loss above. A `<StrictMode>` exemption around the canvas, or
  an R3F upgrade, would fix it; neither was in scope.
- `frontend/CLAUDE.md` says `ACTIONS` maps "all 20 backend actions"; the backend has 25.
  Pre-existing, and correcting it means auditing the table, not editing a number.
- `build_turn` reads office holders as they stand *now* while contracts are reconstructed
  as they stood at that turn (`darwin_db.py`). Pre-existing asymmetry, carried through the
  extraction unchanged because B1 forbade changing any mapping.
- `runs/` has no retention policy, as ADR 2 says. Abandoned sessions accumulate.

## Not in this plan

- **Promotion of a `runs/` trace into `releases/`** with `about.md`, verdicts and scores.
  ADR 2 defers it deliberately; a citable artifact is an act of publication, not a side
  effect of pressing Step.
- **Retention or cleanup of `runs/`.** Named as a consequence in ADR 2 and left open.
- **Judge verdicts in the live view.** The judge runs offline (`backend/app/judge/`); a live
  frame carries `verdict: null` and the panel must show that absence honestly.
- **Layers 1-4** (contracts, production, information markets, social strata) — spec §7
  phases 2-5. This plan is spec Phase 6 plus the disk-trace gap, and adds no mechanic, no
  action and no deception type. Nothing here bumps `PROMPT_VERSION` or `env.version`, so no
  existing response cache is invalidated.
- **Cached re-execution driven from the UI** (spec §5.3). `darwin replay --from-cache`
  already covers it from the CLI.
- **Walk animation between venues.** `Town.tsx` had it; the 3-D pawns are positioned, not
  animated, per spec §6's "agents are positioned, not simulated". Worth a follow-up, not a
  blocker.
- **A headless raster of `WorldFrame`** for paper figures — the stated answer if ADR 1's
  revisit condition fires.

## S1 outcome

**Answer: the panel is docked beside the canvas, and its channels stack vertically.**
ADR 1 stands — the triple stays legible in the 3-D view.

Method: `TurnCard` itself was rendered in both candidate layouts over the live
`WorldScene`, against `releases/leaderboard_335t_20260726` turn 1 (`qwen`, judged
`misdirection`, conf 0.70 — a turn that exercises all four fields). Captured with
Playwright at 1280x800 and 390x844, `deviceScaleFactor: 2`.

What the four captures showed:

| Layout | 1280x800 | 390x844 |
|---|---|---|
| Dock (`lg:grid-cols-[1fr_380px]`) | Readable. All four fields visible without scrolling. | **Best of the four.** Canvas on top, panel below, channels full width. |
| Overlay (absolute, over canvas) | Panel occludes two of six venues (Alley, Lounge) outright. | Broken — panel overflows the canvas box, text clipped mid-sentence. |

Three findings that bind F3:

1. **Overlay is rejected on evidence, not taste.** At 1280x800 it hides a third of the
   world it is explaining. Spec §6 forbids a world that buries the triple; an overlay
   inverts the same failure.
2. **`TurnCard`'s `md:grid-cols-3` must not be reused as-is.** That breakpoint is
   viewport-based, so in a 380px dock on a wide screen it packs three channels into
   ~110px columns — legible but cramped at 3-4 words a line. The same card at 390px
   viewport, where the grid collapses, reads markedly better. F3's `TriplePanel` must
   stack the channels unconditionally and reuse `Channel` alone, not the whole card.
3. **Panel width, not viewport width, is the constraint.** A dock narrower than ~360px
   starts wrapping the judge row; keep 380px as the floor.

Also settled, and it changes F8: **the 3-D scene does not render under `npm run dev`.**
`reactStrictMode: true` (`frontend/next.config.js:3`) double-mounts the R3F `Canvas`; the
first renderer's disposal takes the GL context with it and the surviving canvas reports
`isContextLost() === true`. Reproduced on the committed `main` build in two independent
browsers, so it predates this plan. Under `npm run build && npm start` the same page
renders correctly (`lost: false`). Every visual check in this plan — S1, F3, F8 — runs
against a production build. This is recorded as a pre-existing defect, not fixed here.

Evidence (screenshots, kept out of the repo — a spike keeps no files):
`s1-dock-wide.png`, `s1-dock-narrow.png`, `s1-overlay-wide.png`, `s1-overlay-narrow.png`
in the session scratchpad. Deviation from S1's stated definition of done, which asked for
them appended here; ~1.1 MB of PNGs for a discarded prototype is not worth the repo.
