# CLAUDE.md -- frontend/

Next.js 15 (App Router) + React 19 + Tailwind 3. The frontend is a viewer only; all game logic lives in the backend Oracle. The look is a cozy "tiny town of LLM critters" (cream palette, Fredoka/Nunito/JetBrains Mono).

**Buildings own the action space.** Each venue's action list lives in `shared/venues.json`, which the Oracle reads too; the sign on a building and the prompt an agent standing there received are the same strings. Walk up to one and the panel lists what it is for.

**The world is 3-D everywhere, you are in it, and there is exactly one renderer.** `components/three/` (React Three Fiber) draws both the live session at `/session/[sessionId]` and the replay at `/gallery/[runId]/3d`. It is a playback renderer with no game logic: it reads a `WorldFrame` from `lib/frame.ts` and nothing else, which is what stops the live view and a replayed run from disagreeing about where an agent stood.

Both views open **on foot**: pointer lock to look, WASD to walk, shift to run, and an `overview` toggle for the old orbiting camera. World units are metres — a 52m plaza, 3.6m venue blocks, 1.7m agents, a 1.7m eye height — and that scale is load-bearing, not decoration: it is what makes a building read as a building from the ground. On foot there is no clicking; you read an agent by **walking up to it**, and the panel shows whoever you are standing in front of and nobody when you are alone.

There is no 2-D fallback. `Town.tsx` and the stage critter are gone; a browser without WebGL gets an explicit notice with links to the run as data. That deviates from spec `2026-08-24-layered-economy-and-replay-design.md` §6, which kept the 3-D view additive -- see `docs/adr/2026-08-26-3d-primary-renderer.md` for why, and for the one clause of §6 that got stricter rather than looser: **selecting an agent-turn must show private reasoning, public message, applied action and the judge's verdict, at `TurnCard` readability.** With no second view, that panel is the only place the triple is legible, so it is gated by `e2e/triple.spec.ts` rather than trusted.

## Run

```bash
npm install
npm run dev          # http://localhost:3000
npm run build
npm test             # vitest: pure functions in lib/
npm run test:e2e     # playwright: the triple stays legible (builds first)
```

**The 3-D scene does not render under `npm run dev`.** `reactStrictMode` double-mounts the
R3F canvas and the GL context is lost on the first unmount, leaving an empty canvas. Check
anything visual against `npm run build && npm start`.

Talks to `http://localhost:8000` (REST) and `ws://localhost:8000/ws` (WS). Override via `.env.local`.

## Where things live

- **`app/page.tsx`** -- Landing page. "New simulation" button → `createSession()` → `router.push('/session/{id}')`. No game UI here.
- **`app/session/[sessionId]/page.tsx`** -- The simulation view. Outer shell, header (brand + stat pills + Step/+10/Auto/Share/Export/Config/Reset), main grid `1fr 340px` (3-D world | Roster), logs grid `1fr 1fr` (PublicLog | ThoughtLog), footer keyboard hint, ConfigPanel + pause Dialog. Reads `sessionId` via `useParams`; all fetches hit `/sessions/{id}/...`. Owns the WS connection (`connectOracle(sessionId, ...)`) and auto-play loop. "Share" copies the URL.
- **`app/layout.tsx`** -- Loads Fredoka / Nunito / JetBrains Mono via `next/font/google` and exposes them as CSS variables.
- **`app/globals.css`** -- Design tokens, body dot texture, log-in animation, trust-bar fill, button styles, cozy inputs. The stage critter's anatomy, bubble and dust keyframes went with the 2-D town.
- **`lib/world3d.ts`** -- 3-D geometry: stage-pixel to world-unit mapping at a fixed `WORLD_UNITS_PER_STAGE_PX`, so `GROUND` grows with the generated stage while a building stays 5.2 units across. Also `VENUE_FOOTPRINT`, `agentSlot()` (slots sit *outside* the venue block, or the pawn is drawn behind it), and `hasWebGL()`.
- **`lib/firstPerson.ts`** -- being a body in the town: eye height, walk and run speeds, the keys-and-yaw to displacement rule, and collision against the venue blocks. Pure; the controller owns the camera and the clock, nothing else.
- **`lib/clock.ts`** -- simulation time, mirroring `backend/app/oracle/clock.py`. `BEAT = 1000` ticks. The two must agree or walks render at the wrong speed while every number in the trace still looks right.
- **`lib/motion.ts`** -- easing, walk duration bounds, and which way to face. The body faces **+Z**, deliberately against the three.js -Z convention: the toes and the forward lean point that way, and it puts a resting agent's face toward the overview camera instead of the back of its head.
- **`lib/gait.ts`** -- body proportions in metres, and the walk cycle. The pose is a pure function of ground covered, never of elapsed time; legs swing in opposition and each arm swings with the leg on the other side.
- **`lib/architecture.ts`** -- what each venue is built like: storeys, roof kind, window grid, awning, columns. Every dimension is measured against `VENUE_FOOTPRINT`, which is the box the walker collides with — a building wider than that has eaves you walk through.
- **`lib/proximity.ts`** -- who you are close enough to, and facing, to be reading. Scored by distance divided by how centred they are, so the panel describes the body filling your screen rather than whoever is nearest.
- **`lib/frame.ts`** -- `WorldFrame`, the only thing the renderer sees. Three builders, one per clock: `buildFrameFromSnapshot()` (live), `buildFramesFromTurns()` (v4/v5 trace), and `sampleFrameAtTick()` / `eventFrames()` (v6 event trace). Owns venue assignment, the spouse-follow rule and slot packing. A live frame carries `verdict: null` -- the judge runs offline.
- **`components/three/`** -- `WorldScene` (canvas, lights, ground, fog on foot, and `CameraRig`, which repositions the camera on a mode change because the Canvas `camera` prop is read once at mount), `FirstPersonControls`, `ProximityFocus`, `VenueBlock` (a building with a door, windows, roof and sign, turned to face the plaza), `AgentPawn` (walks to its new position each turn), `AgentBody` (the person: head, torso, swinging limbs), `TriplePanel`, `TurnScrubber`. Pawns and `<Bounds>` do not mix: `Bounds` re-aims the camera to frame its children, so it wraps only the venues, and only in the overview.
- **`components/Triple.tsx`** -- `Channel` and `VerdictRow`, shared by `TurnCard` (2-D turn list) and `TriplePanel` (3-D). Two presentations of the triple would be two instruments.
- **`components/Avatar.tsx`** -- `CritterAvatar`, the roster head beside an agent's name.
- **`lib/worldData.ts`** -- the shared tables, imported from `../shared/*.json` through the `@shared` alias (registered in `tsconfig.json`, `next.config.js` and `vitest.config.mts`). Venue identity, coordinates and per-venue action lists live there, not here.
- **`lib/town.ts`** -- how the town *looks*: 5 `FAMILIES` with color + emoji, per-venue `COSMETICS` (icon, body, roof) with a default for an unstyled venue, and the `COLOR_HEX` agent palette. `VENUES` and `ACTIONS` are derived from `worldData`. 3-D slot geometry is `agentSlot()` in `lib/world3d.ts`, not `venueSlot()` here.
- **`lib/ws.ts`** -- Types (`AgentSnap`, `ThoughtSnap`, `PausedEvent`), `ORACLE_HTTP`, `createSession()`, and `connectOracle(sessionId, onSnapshot, onPaused)` (fetches `/sessions/{id}/state`, opens `/ws/{id}`).
- **`components/Sidebar.tsx`** -- Roster cards: avatar, name + specialty sub-label, balance, **model-id chip** (the OpenRouter model each critter runs — the research variable), gradient trust bar, inventory pills, mood / invested badge, social tags. Dead state grays the card and pins an "OUT" ribbon.
- **`components/PublicLog.tsx`** -- "Town Square" public feed: agent-color dot, bolded name, family-tinted action intent, outcome, optional public_message in italic quote.
- **`components/ThoughtLog.tsx`** -- "Inner Thoughts" private monologue (italic, observer only).
- **`components/ConfigPanel.tsx`** -- Agent setup modal. Takes a `sessionId` prop; posts to `/sessions/{id}/configure`. One session-level **OpenRouter** API key (sent inline as `keys: {openrouter: rawKey}`, encrypted + scoped to the session) + a per-agent **model id** text field (any OpenRouter id, e.g. `openai/gpt-5`). No provider dropdown. Color picker. Balance visibility (public/fuzzy/hidden). Optional personality.

## Two clocks

A run is either **turn-shaped** (v4/v5) or **event-shaped** (v6), and the replay
view picks by asking `/releases/{id}/events` — an empty answer means the old
clock. Old releases are never re-recorded, so both paths stay.

- **Turn-shaped**: one frame per turn, every agent in it, walk duration guessed
  render-side by `walkDuration`. That guess carries no claim: the trace says
  where an agent stood on each turn and nothing about the space between.
- **Event-shaped**: agents act at unrelated moments, so there is no "who acted on
  turn N". Frames are sampled on an even grid of simulation time by
  `eventFrames`, and each `FrameAgent` carries a real walk window
  (`from` / `departsAt` / `arrivesAt`) that the backend charged against the
  clock. `AgentPawn` animates on it, so a journey takes exactly as long as the
  world says it took. Anything else would draw a walk that did not happen.

The current tick reaches the scene as a **ref**, not a prop: it advances every
animation frame during playback, and a state update per frame would re-render
every pawn. Both paths are gated in a real browser — `e2e/triple.spec.ts` for
turns, `e2e/continuous.spec.ts` for the clock.

## Layout

```
+──[Header: 🌱 brand · Turn / Alive / Treasury · Step | +10 | Auto · Export · Config · Reset]──+
|                                                                                              |
|  ┌──────── 3-D world (R3F canvas) ────────┐  ┌─── Roster ───┐                                |
|  │  [overview toggle]                     │  │ agent card   │                                |
|  │  six venue blocks at eye height,       │  │ agent card   │                                |
|  │  agents walking between them,          │  │ ...          │                                |
|  │  [triple card] when one is in front    │  └──────────────┘                                |
|  └────────────────────────────────────────┘                                                  |
|                                                                                              |
|  ┌── Town Square (public feed) ──┐  ┌── Inner Thoughts (private monologues) ──┐               |
|                                                                                              |
|  footer: S Step · Space Auto · R Reset                                                       |
+──────────────────────────────────────────────────────────────────────────────────────────────+
```

The replay view at `/gallery/[runId]/3d` is the same canvas with a turn scrubber under it
and the triple panel docked at `380px` on the right.

## Conventions

- `'use client'` on all components (WS + state requires client rendering).
- **Snapshot is the single source of truth.** Never cache derived state.
- **Agent identity = color** (red, blue, green, etc.). No legacy sprite names. The shirt *and* the sleeves carry it — on the torso alone it is a sliver you cannot pick out across the plaza.
- **`ACTIONS`** in `lib/town.ts` is derived from `shared/actions.json`; the venue, tier and summary come from the backend's own table.
- **Auto-play** runs 1 turn every `AUTO_PLAY_DELAY_MS` (3700ms). Replay playback is faster (700ms): nothing walks, so the only thing to wait for is reading.
- **Config modal auto-opens** when no agents exist (first load or after reset).
- Stage size and venue (x, y) are generated into `shared/`; `STAGE_W`/`STAGE_H` and `GROUND` are derived from them, so a building stays 5.2 world units as the town grows.

## Adding a new action (frontend)

Nothing. `lib/worldData.ts` reads `shared/actions.json`, the same file the Oracle
reads, and `lib/town.ts` derives `ACTIONS` from it. Adding a venue costs an optional
entry in `town.ts::COSMETICS` and `architecture.ts::BY_VENUE` -- both default rather
than crash.

## Styling

Tailwind 3 with a cozy palette (`cozy-*` colors in `tailwind.config.js`) plus tokens in `globals.css`:
- `--bg-1: #FFF4E3` (cream background), `--ink: #4A3A2E` (text), `--accent: #E8956A` (warm peach).
- Buttons via `.btn-cozy` (+ `primary`/`on`/`danger`/`ghost`); `Button` from `components/ui/button.tsx` wraps these.
- Dialogs (`components/ui/dialog.tsx`) inherit cream/ink theme.
- Fonts: Fredoka (display + numbers), Nunito (body), JetBrains Mono (monospace).

## Things NOT to do

- Don't compute balances in the frontend. Oracle is authoritative.
- Don't add a state manager. Snapshot prop pattern is sufficient.
- Don't compute placement in a component. Venue assignment and slot packing live in `lib/frame.ts`; a second copy is how the two views start disagreeing.
- Don't reintroduce a 2-D world renderer as a WebGL fallback. A renderer CI never exercises rots silently (ADR 2026-08-26). The fallback is an honest notice plus the raw trace.
- Don't verify anything visual with `npm run dev` -- the canvas is dead there. Build first.
- Don't put walking, collision or focus logic in a component. It lives in `lib/`, where it is tested without a browser; the components own the camera, the clock and the keyboard.
- Don't let a walk outlive the turn that caused it (`MAX_WALK_SECONDS`) on the **turn** clock. Replay advances every 700ms, and an agent still crossing the plaza from two turns ago is lying about where it is. On the **event** clock the bound does not apply: the walk's duration comes from the trace, and shortening it would show a journey the world did not take.
- Don't size a building by eye. `VENUE_FOOTPRINT` is the collision box; anything past it is scenery you walk through. Put the number in `lib/architecture.ts`, where the invariant is tested.
- Don't drive an animation from elapsed time when it represents movement. Time-driven legs windmill while the body inches along.
- Don't assume an agent faces -Z. The body is +Z-forward; `facingAngle` and the forward lean both depend on it.
- Don't switch camera velocity on and off. `smoothVelocity` ramps it, because an instant start and a dead stop read as jerky at any frame rate; the check for a stopped camera happens *after* smoothing or deceleration never runs.
- Don't use legacy sprite names (scholar, trickster, cipher, etc.). Use color names only.
- Don't time-stamp log rows with `Date.now()` during render -- it jitters every snapshot.
