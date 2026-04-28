# CLAUDE.md — frontend/

Next.js 15 (App Router) + React 19 + Tailwind 3 + Phaser 3. The frontend is a **viewer**, not a participant — all game logic lives in the backend Oracle. The frontend mirrors state via WebSocket and dispatches turn requests via REST.

## Run

```bash
npm install
npm run dev          # http://localhost:3000
npm run typecheck
npm run build
```

By default the app talks to `http://localhost:8000` (REST) and `ws://localhost:8000/ws` (WebSocket). Override via `frontend/.env.local`:

```
NEXT_PUBLIC_ORACLE_HTTP=https://my-oracle.example.com
NEXT_PUBLIC_ORACLE_WS=wss://my-oracle.example.com/ws
```

## Where things live

- **`app/page.tsx`** — Single-page client component. Owns the WS connection and the snapshot state. Passes snapshot down to `<Sidebar>`, `<ThoughtLog>`, and `<Arena>` as props.
- **`components/Arena.tsx`** — Thin React wrapper. Mounts the Phaser game once, then forwards snapshot updates to the scene.
- **`components/Sidebar.tsx`, `ThoughtLog.tsx`** — Pure presentational components reading from snapshot props.
- **`lib/ws.ts`** — `connectOracle(onSnapshot)` — opens WS, auto-reconnects on close, also pulls initial state via REST. **All shared TS types live here** (`AgentSnap`, `WorldSnapshot`, etc.).
- **`lib/phaser/scene.ts`** — Phaser scene as a module-level singleton. Lives outside React. `ensureGame(parent)` is idempotent; `syncSnapshot(snap)` is called from React effects.

## React ↔ Phaser bridge

The two systems have **incompatible lifecycles** — React re-renders on every state change, Phaser owns its own render loop. The pattern:

- React owns the snapshot (state)
- Phaser owns the canvas (DOM + animation)
- `<Arena>` calls `syncSnapshot()` in a `useEffect` whenever the snapshot prop changes
- The Phaser scene reads the snapshot, diffs against its own sprite map, and updates positions / labels / thought bubbles

**Don't try to drive Phaser from React state directly.** Don't mount the Phaser game inside a child component that re-renders. `ensureGame` is the only entry point; it lazy-imports Phaser (browser-only).

## Conventions

- **Every file with state, effects, or browser globals must start with `'use client';`** — Next.js App Router defaults to server components, which break Phaser and `WebSocket`.
- **Phaser is dynamically imported.** `<Arena>` is loaded with `dynamic(..., { ssr: false })` from `app/page.tsx`. Don't import `phaser` at the top of any component file — it touches `window` and crashes SSR.
- **Snapshot is the single source of truth.** Components compute everything from `snapshot.agents` / `snapshot.recent_thoughts`. Don't cache derived state across renders.
- **Sprite styling lives in `scene.ts`.** `SPRITE_COLORS` (by sprite kind) and `POS_GRID` (by agent_id) are the two knobs. New agent → add an entry in both.
- **WS reconnects automatically.** Don't add custom retry logic in components — `connectOracle` already handles it with a 1.5s backoff.

## Adding a new component

If it reads snapshot:
1. Take `snapshot: WorldSnapshot | null` as a prop (don't subscribe to WS yourself)
2. Mark it `'use client';` only if it has state or effects — pure renderers can stay server components, but in this app everything is client because of WS

If it triggers an Oracle action: use `fetch(\`${process.env.NEXT_PUBLIC_ORACLE_HTTP}/...\`)`. Don't add an API client abstraction — the surface is small enough.

## Styling

Tailwind 3 with a custom palette (`arena.bg`, `arena.panel`, `arena.accent`). The pixel-art aesthetic is intentional:

- `image-rendering: pixelated` is set globally on Phaser canvases (in `globals.css`)
- Use Tailwind utility classes, not CSS modules
- Font is monospace by default; the `font-pixel` class is reserved for headers if you import Press Start 2P later

## Gotchas

- **`ssr: false` is mandatory for `<Arena>`.** Without it, Next.js tries to render Phaser server-side and crashes on `window`.
- **Strict mode double-mounts in dev.** `useEffect` runs twice — `ensureGame` is idempotent so this is fine, but if you add side-effecting init logic, guard it.
- **WebSocket origin must match.** If you put the Oracle behind a proxy or change the port, update both `NEXT_PUBLIC_ORACLE_HTTP` and `NEXT_PUBLIC_ORACLE_WS` — they're independent.
- **Don't store snapshot in `localStorage`.** It's stale by definition; always wait for the WS snapshot or REST `/state` to populate.

## Things NOT to do

- **Don't compute balances or wealth share in the frontend.** The Oracle is authoritative. Display what `snapshot.agents[i].balance` says.
- **Don't add a state manager (Redux / Zustand / Jotai).** The snapshot prop pattern is sufficient — there's exactly one piece of global state and it changes ~once per second.
- **Don't import `phaser` at the top of any file other than `lib/phaser/scene.ts`.** Even `import type` from Phaser at the wrong place can pull the runtime into the SSR bundle.
- **Don't add a build step that bundles Phaser server-side.** If `next build` starts complaining about `window is not defined`, you've imported Phaser somewhere reachable from a server component.
