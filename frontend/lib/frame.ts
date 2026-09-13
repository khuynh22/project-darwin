import { BEAT } from '@/lib/clock';
import type { ReleaseEvent, ReleaseTurn, Verdict } from '@/lib/releases';
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
  /**
   * The walk that brought it here, in simulation ticks.
   *
   * `arrivesAt === departsAt` means standing still — either it did not move or
   * the frame came from a live snapshot, which carries no clock. The renderer
   * falls back to its own easing in that case; when the window is real it
   * animates on it, so the journey takes as long as the world says it took.
   */
  from: Vec3;
  departsAt: number;
  arrivesAt: number;
};

export type WorldFrame = {
  /** Agent moves, for a turn-based frame. Zero for a tick-sampled one. */
  turn: number;
  /** Simulation time. Zero for a live snapshot, which has no clock. */
  tick: number;
  agents: FrameAgent[];
};

/** One agent acting, read off a v6 trace. */
export type EventRow = {
  eventId: number;
  tick: number;
  agentSeq: number;
  agentId: string;
  action: string;
  venue: string;
  travelTicks: number;
  deliberationTicks: number;
  monologue: string;
  publicMessage: string;
  outcome: string;
  balance: number | null;
  trustScore: number | null;
  spouseId: string | null;
};

const EMPTY_FRAME: WorldFrame = { turn: 0, tick: 0, agents: [] };
const PALETTE = Object.values(COLOR_HEX);

/** What placement needs to know about an agent, from either source. */
type Placeable = {
  agentId: string;
  action: string;
  spouseId: string | null;
  /** Authoritative venue from a v6 trace. Falls back to the action mapping. */
  venueId?: string;
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
    row.venueId ?? actionDef(row.action)?.venue ?? HOME_VENUES[index % HOME_VENUES.length];

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
    tick: 0,
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
        from: spot.position,
        departsAt: 0,
        arrivesAt: 0,
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
        tick: 0,
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
            from: spot.position,
            departsAt: 0,
            arrivesAt: 0,
          };
        }),
      };
    });
}

/**
 * The world at one instant of simulation time.
 *
 * This is what the continuous clock buys the renderer. A turn-based frame could
 * only ask "who acted on turn N", and once agents wake at their own pace that
 * question has no single answer — the agents in a turn bucket acted at
 * unrelated moments. A tick has one: every agent is somewhere at tick T, either
 * standing at a venue or partway along a walk to it.
 *
 * Each agent's state comes from its own latest event at or before `tick`, so
 * agents that have not moved for a long time simply stay where they were.
 */
export function sampleFrameAtTick(
  events: EventRow[],
  tick: number,
  verdicts: Verdict[] = [],
): WorldFrame {
  if (events.length === 0) return { ...EMPTY_FRAME, tick };

  const colors = paletteColors(events.map((e) => e.agentId));
  const verdictAt = new Map(verdicts.map((v) => [`${v.turn}:${v.agent_id}`, v]));

  const history = new Map<string, EventRow[]>();
  for (const e of events) {
    const list = history.get(e.agentId);
    if (list) list.push(e);
    else history.set(e.agentId, [e]);
  }
  for (const list of history.values()) list.sort((a, b) => a.tick - b.tick);

  const current = new Map<string, { now: EventRow; before: EventRow | null }>();
  for (const [agentId, list] of history) {
    let index = -1;
    for (let i = 0; i < list.length && list[i].tick <= tick; i += 1) index = i;
    // Before its first event an agent has not entered the world yet.
    if (index < 0) continue;
    current.set(agentId, { now: list[index], before: index > 0 ? list[index - 1] : null });
  }

  const rows = [...current.entries()].map(([agentId, { now }]) => ({
    agentId,
    action: now.action,
    spouseId: now.spouseId,
    venueId: now.venue,
  }));
  const toPlaced = place(rows);
  // Where each agent came from, placed under the same law, so a walk starts at
  // the slot the agent actually occupied rather than the centre of a venue.
  const fromPlaced = place(
    [...current.entries()].map(([agentId, { now, before }]) => ({
      agentId,
      action: before?.action ?? now.action,
      spouseId: before?.spouseId ?? now.spouseId,
      venueId: before?.venue ?? now.venue,
    })),
  );

  return {
    turn: 0,
    tick,
    agents: [...current.entries()].map(([agentId, { now }]) => {
      const spot = toPlaced.get(agentId)!;
      const departsAt = now.tick + now.deliberationTicks;
      return {
        agentId,
        color: colors.get(agentId) ?? PALETTE[0],
        venueId: spot.venue.id,
        position: spot.position,
        action: now.action,
        balance: now.balance,
        trustScore: now.trustScore,
        monologue: now.monologue,
        publicMessage: now.publicMessage,
        outcome: now.outcome,
        verdict: verdictAt.get(`${now.agentSeq}:${agentId}`) ?? null,
        from: fromPlaced.get(agentId)?.position ?? spot.position,
        departsAt,
        arrivesAt: departsAt + now.travelTicks,
      };
    }),
  };
}

/** Simulation time spanned by a trace, for a scrubber to range over. */
export function tickRange(events: EventRow[]): { first: number; last: number } {
  if (events.length === 0) return { first: 0, last: 0 };
  let first = events[0].tick;
  let last = events[0].tick;
  for (const e of events) {
    if (e.tick < first) first = e.tick;
    // The walk and the action both outlast the event that started them.
    const end = e.tick + e.deliberationTicks + e.travelTicks;
    if (end > last) last = end;
  }
  return { first, last };
}

/**
 * How finely a run is sampled for the scrubber.
 *
 * Every sample is a frame the transport can land on, so this trades scrub
 * resolution against how many frames a long run builds. It does not affect how
 * smooth a walk looks: the pawn interpolates from the live tick between
 * samples, not from one sample to the next.
 */
export const SAMPLE_BEATS = 0.5;

/**
 * A whole event-shaped run as evenly spaced frames.
 *
 * Sampling on a fixed grid rather than one frame per event is what keeps the
 * transport meaningful. One frame per event would advance the clock by however
 * long the next agent happened to sleep, so playback would lurch, and a scrub
 * bar would give more room to a busy stretch than to a quiet one.
 */
export function eventFrames(
  events: EventRow[],
  verdicts: Verdict[] = [],
  sampleBeats: number = SAMPLE_BEATS,
): WorldFrame[] {
  if (events.length === 0) return [];
  const { first, last } = tickRange(events);
  const stepTicks = Math.max(1, Math.round(sampleBeats * BEAT));
  const out: WorldFrame[] = [];
  for (let t = first; t <= last; t += stepTicks) {
    out.push(sampleFrameAtTick(events, t, verdicts));
  }
  // The closing instant, so the last action is not cut off by the step size.
  if (out.length === 0 || out[out.length - 1].tick < last) {
    out.push(sampleFrameAtTick(events, last, verdicts));
  }
  return out;
}

/** The wire shape of a v6 event, narrowed to what the renderer needs. */
export function toEventRows(rows: ReleaseEvent[]): EventRow[] {
  return rows.map((r) => ({
    eventId: r.event_id,
    tick: r.tick,
    agentSeq: r.agent_seq,
    agentId: r.agent_id,
    action: r.action,
    venue: r.venue,
    travelTicks: r.travel_ticks,
    deliberationTicks: r.deliberation_ticks,
    monologue: r.monologue,
    publicMessage: r.public_message,
    outcome: r.outcome,
    balance: r.state?.balance ?? null,
    trustScore: r.state?.trust_score ?? null,
    spouseId: r.state?.spouse_id ?? null,
  }));
}
