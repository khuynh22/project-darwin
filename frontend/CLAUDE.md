# CLAUDE.md -- frontend/

Next.js 15 (App Router) + React 19 + Tailwind 3. Pure React UI -- **no Phaser, no canvas**. The frontend is a viewer only; all game logic lives in the backend Oracle.

## Run

```bash
npm install
npm run dev          # http://localhost:3000
npm run build
```

Talks to `http://localhost:8000` (REST) and `ws://localhost:8000/ws` (WS). Override via `.env.local`.

## Where things live

- **`app/page.tsx`** -- Main layout. Owns WS connection, snapshot state, auto-play loop, pause modal. No Phaser.
- **`components/WorldMap.tsx`** -- 6 venue cards (Work, Bank, Casino, Market, Lounge, Alley) in a 3x2 grid. Agents shown as styled chips with initials, name, provider, balance, specialty, and current action.
- **`components/Sidebar.tsx`** -- Agent cards: cash + invested, trust bar, inventory, specialty badge, social state, status badges.
- **`components/PublicLog.tsx`** -- Public feed: actions + outcomes + public_message broadcasts. Color-coded by action type.
- **`components/ThoughtLog.tsx`** -- Private reasoning (observer only). Shows agent monologue/strategy.
- **`components/ConfigPanel.tsx`** -- Agent setup modal. Per-provider API keys (enter once, reused). Color picker. Optional personality.
- **`lib/ws.ts`** -- Types (`AgentSnap` with trust_score, inventory, specialty, invested; `ThoughtSnap` with public_message; `PausedEvent`) + `connectOracle()`.

## Layout

```
+--[Header: Darwin | Turn N | Step | +10 | Auto | Export | Config | Reset]--+
|                                                                    |       |
|  [Work]        [Bank]          [Casino]                            | Agent |
|  agent chips   agent chips     agent chips                         | Cards |
|                                                                    |       |
|  [Market]      [Lounge]        [Alley]                             |       |
|  agent chips   agent chips     agent chips                         |       |
|                                                                    |       |
+--[Public Feed]-------------+--[Private Thoughts]-------------------+-------+
```

## Conventions

- **`'use client'`** on all components (WS + state requires client rendering).
- **Snapshot is the single source of truth.** Never cache derived state.
- **Agent identity = color** (red, blue, green, etc.). No legacy sprite names (scholar, robot, etc.).
- **`ACTION_VENUE`** in `WorldMap.tsx` maps all 20 actions to 6 venues.
- **Auto-play** runs 1 turn every 500ms via `setTimeout` loop. Stops on error/apex.
- **Config modal auto-opens** when no agents exist (first load or after reset).

## Adding a new action (frontend)

1. `WorldMap.tsx::ACTION_VENUE` -- map action name to venue (workplace, bank, casino, marketplace, lounge, alley)
2. `WorldMap.tsx::ACTION_LABELS` -- human-readable label for the action chip
3. `PublicLog.tsx::ACTION_COLORS` -- color class for the public feed

## Styling

Tailwind 3 with zinc palette. System font (not monospace). Dark theme (#09090b base). Custom scrollbars. No pixel art.

## Things NOT to do

- Don't compute balances in the frontend. Oracle is authoritative.
- Don't add a state manager. Snapshot prop pattern is sufficient.
- Don't add Phaser or any canvas library. Pure React + CSS.
- Don't use legacy sprite names (scholar, trickster, cipher, etc.). Use color names only.
