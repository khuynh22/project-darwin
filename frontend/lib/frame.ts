import type { ReleaseTurn, Verdict } from '@/lib/releases';
import { COLOR_HEX, HOME_VENUES, VENUES, actionDef, type Venue } from '@/lib/town';
import { agentSlot, type Vec3 } from '@/lib/world3d';
import type { AgentSnap, WorldSnapshot } from '@/lib/ws';

/**
 * One agent, at one turn, ready to render.
 *
 * The renderer sees only this — never a `WorldSnapshot` and never a
 * `ReleaseTurn`. That is what lets one scene serve both the live session and a
 * replayed run without either source leaking a shape into the other.
 */
export type FrameAgent = {
  agentId: string;
  color: string;
  venueId: string;
  position: Vec3;
  action: string;
  balance: number | null;
  trustScore: number | null;
  monologue: string;
  publicMessage: string;
  outcome: string;
  /** Null in a live frame: the judge runs offline, after the run. */
  verdict: Verdict | null;
};

export type WorldFrame = {
  turn: number;
  agents: FrameAgent[];
};

const EMPTY_FRAME: WorldFrame = { turn: 0, agents: [] };
const PALETTE = Object.values(COLOR_HEX);

/** What placement needs to know about an agent, from either source. */
type Placeable = {
  agentId: string;
  action: string;
  spouseId: string | null;
};

/**
 * Venue assignment, the spouse-follow rule, and slot packing — the one
 * placement law, applied identically to a live snapshot and to a trace.
 *
 * Two agents at the same venue must not stand at the same point, and an agent
 * must not jump across the plaza because a neighbour arrived, so ordering is by
 * agent id rather than by arrival.
 */
function place(rows: Placeable[]): Map<string, { venue: Venue; position: Vec3 }> {
  const sorted = [...rows].sort((a, b) => a.agentId.localeCompare(b.agentId));

  const venueIdFor = (row: Placeable, index: number): string =>
    actionDef(row.action)?.venue ?? HOME_VENUES[index % HOME_VENUES.length];

  const groups: Record<string, string[]> = {};
  for (const venue of VENUES) groups[venue.id] = [];

  sorted.forEach((row, index) => {
    let venueId = venueIdFor(row, index);
    if (row.spouseId) {
      const spouseIndex = sorted.findIndex((r) => r.agentId === row.spouseId);
      if (spouseIndex >= 0) {
        // The lower agent id picks; the partner mirrors. Both sides run this,
        // so the rule has to pick the same venue from either seat.
        venueId =
          row.agentId < row.spouseId
            ? venueId
            : venueIdFor(sorted[spouseIndex], spouseIndex);
      }
    }
    groups[venueId].push(row.agentId);
  });

  const placed = new Map<string, { venue: Venue; position: Vec3 }>();
  for (const venue of VENUES) {
    const occupants = groups[venue.id];
    occupants.forEach((agentId, slot) => {
      placed.set(agentId, {
        venue,
        position: agentSlot(venue, slot, occupants.length),
      });
    });
  }
  return placed;
}

/** Stable colour for a trace, which carries no palette of its own. */
function paletteColors(agentIds: string[]): Map<string, string> {
  const ordered = [...new Set(agentIds)].sort((a, b) => a.localeCompare(b));
  return new Map(ordered.map((id, i) => [id, PALETTE[i % PALETTE.length]]));
}

export function buildFrameFromSnapshot(snap: WorldSnapshot | null): WorldFrame {
  if (!snap) return EMPTY_FRAME;

  const alive: AgentSnap[] = snap.agents.filter((a) => a.alive);

  // `recent_thoughts` is a newest-first rolling window, so the first entry per
  // agent is that agent's latest action.
  const latest = new Map<string, WorldSnapshot['recent_thoughts'][number]>();
  for (const t of snap.recent_thoughts) {
    if (!latest.has(t.agent_id)) latest.set(t.agent_id, t);
  }

  const placed = place(
    alive.map((a) => ({
      agentId: a.agent_id,
      action: latest.get(a.agent_id)?.action ?? '',
      spouseId: a.spouse,
    })),
  );

  return {
    turn: snap.turn,
    agents: alive.map((a) => {
      const spot = placed.get(a.agent_id)!;
      const thought = latest.get(a.agent_id);
      return {
        agentId: a.agent_id,
        color: COLOR_HEX[a.sprite] ?? PALETTE[0],
        venueId: spot.venue.id,
        position: spot.position,
        action: thought?.action ?? '',
        balance: a.balance,
        trustScore: a.trust_score,
        monologue: thought?.monologue ?? '',
        publicMessage: thought?.public_message ?? '',
        outcome: thought?.outcome ?? '',
        verdict: null,
      };
    }),
  };
}

export function buildFramesFromTurns(
  turns: ReleaseTurn[],
  verdicts: Verdict[] = [],
): WorldFrame[] {
  if (turns.length === 0) return [];

  const colors = paletteColors(turns.map((t) => t.agent_id));
  const verdictAt = new Map(verdicts.map((v) => [`${v.turn}:${v.agent_id}`, v]));

  const byTurn = new Map<number, ReleaseTurn[]>();
  for (const t of turns) {
    const list = byTurn.get(t.turn);
    if (list) list.push(t);
    else byTurn.set(t.turn, [t]);
  }

  return [...byTurn.keys()]
    .sort((a, b) => a - b)
    .map((turn) => {
      const rows = byTurn.get(turn)!;
      const placed = place(
        rows.map((t) => ({
          agentId: t.agent_id,
          action: t.action,
          spouseId: t.state.spouse_id,
        })),
      );
      return {
        turn,
        agents: rows.map((t) => {
          const spot = placed.get(t.agent_id)!;
          return {
            agentId: t.agent_id,
            color: colors.get(t.agent_id) ?? PALETTE[0],
            venueId: spot.venue.id,
            position: spot.position,
            action: t.action,
            balance: t.state.balance,
            trustScore: t.state.trust_score,
            monologue: t.monologue,
            publicMessage: t.public_message,
            outcome: t.outcome,
            verdict: verdictAt.get(`${turn}:${t.agent_id}`) ?? null,
          };
        }),
      };
    });
}
