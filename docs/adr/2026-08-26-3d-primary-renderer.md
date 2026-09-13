# ADR 1: Which renderer draws the world, and does the 2-D town survive?

- **Status:** accepted
- **Date:** 2026-08-26
- **Deciders:** repository owner (product intent), tech-lead (decomposition)

## Context

`docs/superpowers/specs/2026-08-24-layered-economy-and-replay-design.md` §6 fixes the 3-D
view as an *additional* gallery route that "must degrade to the 2-D view when WebGL is
unavailable", and states it is "never a replacement". `frontend/CLAUDE.md` repeats the
rule and scopes `components/three/` to the gallery.

The product intent has since changed: the 3-D view is to be the world view everywhere,
including the live session at `/session/[sessionId]`, and the 2-D stage is to be removed
rather than kept as a fallback. That is a deliberate deviation from §6 and it deletes
working code, so it is recorded here rather than left to a diff.

The tension is not 2-D versus 3-D aesthetics. It is:

- **One placement law versus two.** Venue assignment, the spouse-follow rule and slot
  packing live inside `frontend/components/Town.tsx:37-70` today. Keeping both renderers
  means that law is implemented twice against two different data shapes
  (`WorldSnapshot` over WebSocket, `ReleaseTurn[]` over REST), and the two will drift.
  A drifted placement is not a cosmetic bug: an agent shown at the wrong venue misreads
  its action, which is the thing the instrument exists to display.
- **Reachability versus a single code path.** §6's fallback exists because a viewer
  without WebGL currently still sees the run. Deleting the 2-D stage removes that.

## Constraints

- 6 venues, 3-10 agents, fixed 780x560 logical stage (`frontend/lib/town.ts:46-66`).
  Nothing here is large enough for rendering cost to decide the question.
- Frontend CI runs lint, typecheck and build only (`.github/workflows/ci.yml`). There is
  no frontend test runner, so today a renderer's *behaviour* is verified by nobody.
- The 2-D stage is 302 lines (`Town.tsx`) plus 282 (`Critter.tsx`). `Critter.tsx` also
  exports `CritterAvatar`, used at `Sidebar.tsx:86,159,215` and `ConfigPanel.tsx:231`.
  The avatar is a roster head, not a stage critter, and is not in scope for deletion.
- The 3-D scene is 104 lines today (`WorldScene.tsx` + `VenueBlock.tsx`) and renders
  venues only: no agents, no turn cursor, no triple panel.
- React Three Fiber, drei and three are already dependencies (`frontend/package.json`);
  this decision adds no new dependency.
- The largest released trace is 2,010 lines / 335 turns
  (`releases/leaderboard_335t_20260726/trace.jsonl`).

## Options

### A. Keep §6 — 3-D additive, 2-D canonical

Finish the gallery 3-D route; live session stays 2-D. Cheapest, matches the approved
spec, keeps WebGL-less viewers whole. Costs: the placement law stays duplicated, and the
live view — the one a user actually watches — never becomes 3-D, which is the request.

### B. One 3-D renderer everywhere, 2-D stage deleted

`Town.tsx` and the stage half of `Critter.tsx` are removed. Both the live session and the
gallery replay mount the same `WorldScene`, fed by one view-model. Placement logic moves
out of the renderer into `frontend/lib/frame.ts` so it is source-agnostic and testable.
Costs: no WebGL means no world, and §6's degradation clause is void.

### C. One 3-D renderer, 2-D stage retained as fallback only

B, but `Town.tsx` survives behind `hasWebGL()`. Keeps reachability. Costs: two renderers
to keep in step forever, for a path nobody exercises in CI — the drift risk in full,
without the maintenance saving.

## Decision

**Option B.** The 3-D scene is the only world renderer, in the live session and in gallery
replay. `frontend/components/Town.tsx` and the stage rendering in
`frontend/components/Critter.tsx` are deleted; `CritterAvatar` is extracted and kept.

Both views are fed by a single view-model, `WorldFrame`, built in `frontend/lib/frame.ts`
from either a live `WorldSnapshot` or a released `ReleaseTurn[]`. The renderer consumes
only `WorldFrame` and holds no game logic, preserving the §2 non-negotiable that the
Oracle stays authoritative.

Two clauses of §6 are overridden and this ADR supersedes them: "never a replacement" and
the 2-D degradation fallback. The remaining §6 clause is *strengthened*, not relaxed:
selecting an agent-turn must show private reasoning, public message, applied action and
the judge verdict at the readability of the current `TurnCard`. With no 2-D view left to
fall back to, that panel is now the only place the triple is legible, so it is a blocking
acceptance criterion rather than a quality bar.

Viewers without WebGL get an explicit, non-silent capability notice with a link to the
raw trace and the existing thoughts export — not a rendered world. `hasWebGL()`
(`frontend/lib/world3d.ts:52`) already gates the mount and stays.

## Rejected

Option C is the strongest rejected argument: it is the only option that keeps every
viewer able to see a run, and reachability is a real user-facing property that a research
artifact benefits from. It was rejected because a fallback renderer that CI never
exercises and a maintainer never opens is a fallback in name only — it will rot, and it
will rot silently, while charging full maintenance price against every change to the
placement law. Given the choice between an honest capability notice and a rotting second
renderer, the notice is more truthful about what the tool does.

## Consequences

- **Becomes easy:** one placement law, in one file, with one set of tests; live and
  replay views cannot disagree about where an agent stood; new venues, offices and layer-4
  tiers (spec §3) are added once.
- **Becomes hard:** any viewer without WebGL — locked-down enterprise browsers, some
  headless capture paths, older mobile — cannot see a run at all. Screenshot and
  paper-figure workflows now depend on a GPU context. Reviewers reproducing figures
  need a WebGL-capable environment or must read the trace directly.
- **Becomes expensive to reverse:** restoring a 2-D stage means rewriting ~580 deleted
  lines against `WorldFrame` rather than against `WorldSnapshot`. Git history holds the
  old code, but not a version that speaks the new contract.

## Revisit when

A WebGL-unavailable viewer is observed on a path that matters — specifically, if the
capability notice is reached in a paper-figure or CI screenshot workflow, or if a reader
reports being unable to open a released run. At that point the answer is a headless
raster of `WorldFrame`, not a resurrected `Town.tsx`.
