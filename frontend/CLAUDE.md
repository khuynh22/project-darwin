# CLAUDE.md -- frontend/

Next.js 15 (App Router) + React 19 + Tailwind 3. Pure React UI -- **no Phaser, no canvas**. The frontend is a viewer only; all game logic lives in the backend Oracle. The look is a cozy "tiny town of LLM critters" (cream palette, Fredoka/Nunito/JetBrains Mono).

## Run

```bash
npm install
npm run dev          # http://localhost:3000
npm run build
```

Talks to `http://localhost:8000` (REST) and `ws://localhost:8000/ws` (WS). Override via `.env.local`.

## Where things live

- **`app/page.tsx`** -- Landing page. "New simulation" button → `createSession()` → `router.push('/session/{id}')`. No game UI here.
- **`app/session/[sessionId]/page.tsx`** -- The simulation view. Outer shell, header (brand + stat pills + Step/+10/Auto/Share/Export/Config/Reset), main grid `1fr 340px` (Town | Roster), logs grid `1fr 1fr` (PublicLog | ThoughtLog), footer keyboard hint, ConfigPanel + pause Dialog. Reads `sessionId` via `useParams`; all fetches hit `/sessions/{id}/...`. Owns the WS connection (`connectOracle(sessionId, ...)`) and auto-play loop. "Share" copies the URL.
- **`app/layout.tsx`** -- Loads Fredoka / Nunito / JetBrains Mono via `next/font/google` and exposes them as CSS variables.
- **`app/globals.css`** -- Design tokens, body dot texture, critter anatomy keyframes, bubble morph, dust puff, delta float, log-in animation, button styles, cozy inputs.
- **`lib/town.ts`** -- Single source for town data: 6 `VENUES` (work, market, bank, casino, lounge, alley) at fixed `(x,y)` in a 780×560 stage, 5 `FAMILIES` (economy/prosocial/aggression/deception/social) with color + emoji, `ACTIONS` mapping every backend action id → `{family, emoji, venue, intent}`, `COLOR_HEX` agent palette, `venueSlot()` slot offsets so multiple critters share a venue without overlapping.
- **`lib/ws.ts`** -- Types (`AgentSnap`, `ThoughtSnap`, `PausedEvent`), `ORACLE_HTTP`, `createSession()`, and `connectOracle(sessionId, onSnapshot, onPaused)` (fetches `/sessions/{id}/state`, opens `/ws/{id}`).
- **`components/Town.tsx`** -- The town stage. Renders venue houses + center plaza + critters. Places each agent at its action's venue slot. Honors the spouse-follow rule (lower agent_id picks, partner mirrors).
- **`components/Critter.tsx`** -- The CSS-blob critter: body, face, legs, oval shadow, dust puffs, thought bubble. Drives motion with `requestAnimationFrame` + easeInOutCubic + perpendicular sway + settle bounce. Exports `CritterAvatar` for the small head used in roster cards and config panel.
- **`components/Sidebar.tsx`** -- Roster cards: avatar, name + specialty sub-label, balance, gradient trust bar, inventory pills, mood / invested badge, social tags. Dead state grays the card and pins an "OUT" ribbon.
- **`components/PublicLog.tsx`** -- "Town Square" public feed: agent-color dot, bolded name, family-tinted action intent, outcome, optional public_message in italic quote.
- **`components/ThoughtLog.tsx`** -- "Inner Thoughts" private monologue (italic, observer only).
- **`components/ConfigPanel.tsx`** -- Agent setup modal. Takes a `sessionId` prop; posts to `/sessions/{id}/configure`. One session-level **OpenRouter** API key (sent inline as `keys: {openrouter: rawKey}`, encrypted + scoped to the session) + a per-agent **model id** text field (any OpenRouter id, e.g. `openai/gpt-5`). No provider dropdown. Color picker. Balance visibility (public/fuzzy/hidden). Optional personality.

## Layout

```
+──[Header: 🌱 brand · Turn / Alive / Treasury · Step | +10 | Auto · Export · Config · Reset]──+
|                                                                                              |
|  ┌────── Town (780×560 stage in a cream card) ──────┐  ┌─── Roster ───┐                      |
|  │      Work                                          │  │ critter card │                      |
|  │  Alley     Market                                  │  │ critter card │                      |
|  │       Turn N                                       │  │ critter card │                      |
|  │  Lounge    Bank                                    │  │ ...          │                      |
|  │      Casino                                        │  └──────────────┘                      |
|  │  critters absolutely positioned + walk-animated   │                                          |
|  └────────────────────────────────────────────────────┘                                          |
|                                                                                              |
|  ┌── Town Square (public feed) ──┐  ┌── Inner Thoughts (private monologues) ──┐                  |
|                                                                                              |
|  footer: S Step · Space Auto · R Reset                                                       |
+──────────────────────────────────────────────────────────────────────────────────────────────+
```

## Conventions

- `'use client'` on all components (WS + state requires client rendering).
- **Snapshot is the single source of truth.** Never cache derived state.
- **Agent identity = color** (red, blue, green, etc.). No legacy sprite names.
- **`ACTIONS`** in `lib/town.ts` maps all 20 backend actions to venues + family + intent label.
- **Auto-play** runs 1 turn every `AUTO_PLAY_DELAY_MS` (3700ms) -- gives walks time to land before the next turn.
- **Config modal auto-opens** when no agents exist (first load or after reset).
- Stage is fixed 780×560 px logical; venue (x, y) coordinates live in `VENUES`.

## Adding a new action (frontend)

1. `lib/town.ts::ACTIONS` -- add `{family, emoji, venue, intent}` for the new action id.
2. That's it. The town, roster, and public log all read from this table.

## Styling

Tailwind 3 with a cozy palette (`cozy-*` colors in `tailwind.config.js`) plus tokens in `globals.css`:
- `--bg-1: #FFF4E3` (cream background), `--ink: #4A3A2E` (text), `--accent: #E8956A` (warm peach).
- Buttons via `.btn-cozy` (+ `primary`/`on`/`danger`/`ghost`); `Button` from `components/ui/button.tsx` wraps these.
- Dialogs (`components/ui/dialog.tsx`) inherit cream/ink theme.
- Fonts: Fredoka (display + numbers), Nunito (body), JetBrains Mono (monospace).

## Things NOT to do

- Don't compute balances in the frontend. Oracle is authoritative.
- Don't add a state manager. Snapshot prop pattern is sufficient.
- Don't add Phaser, canvas, or any sprite library. Pure React + CSS.
- Don't use legacy sprite names (scholar, trickster, cipher, etc.). Use color names only.
- Don't time-stamp log rows with `Date.now()` during render -- it jitters every snapshot.
