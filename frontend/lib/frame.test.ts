import { describe, expect, it } from 'vitest';
import {
  buildFrameFromSnapshot,
  buildFramesFromTurns,
  type WorldFrame,
} from '@/lib/frame';
import type { ReleaseTurn, Verdict } from '@/lib/releases';
import type { AgentSnap, WorldSnapshot } from '@/lib/ws';

function agent(id: string, over: Partial<AgentSnap> = {}): AgentSnap {
  return {
    agent_id: id,
    display_name: id.toUpperCase(),
    provider: 'openrouter',
    model: 'm/one',
    balance: 10,
    alive: true,
    spouse: null,
    allies: [],
    enemies: [],
    sprite: 'blue',
    consecutive_errors: 0,
    last_error: null,
    trust_score: 50,
    steal_count: 0,
    inventory: {},
    specialty: 'ore',
    invested: 0,
    rest_bonus: false,
    will_target: null,
    ...over,
  };
}

function snapshot(
  agents: AgentSnap[],
  thoughts: WorldSnapshot['recent_thoughts'] = [],
  turn = 4,
): WorldSnapshot {
  return { turn, agents, recent_thoughts: thoughts };
}

function thought(agent_id: string, action: string, turn = 4) {
  return {
    turn,
    agent_id,
    action,
    monologue: `${agent_id} thinks`,
    public_message: `${agent_id} says`,
    outcome: 'ok',
    arguments: {},
  };
}

function turnRecord(
  turn: number,
  agent_id: string,
  action: string,
  over: Partial<ReleaseTurn> = {},
): ReleaseTurn {
  return {
    turn,
    agent_id,
    action,
    monologue: `${agent_id} thinks`,
    public_message: `${agent_id} says`,
    outcome: 'ok',
    arguments: {},
    state: {
      balance: 10,
      trust_score: 50,
      inventory: {},
      alive: null,
      spouse_id: null,
    },
    instrument: { tool_call_ok: true, note: '' },
    ...over,
  };
}

const venueOf = (frame: WorldFrame, id: string) =>
  frame.agents.find((a) => a.agentId === id)?.venueId;

describe('buildFrameFromSnapshot', () => {
  it('places each agent at the venue of its latest action', () => {
    const frame = buildFrameFromSnapshot(
      snapshot(
        [agent('a0'), agent('a1')],
        [thought('a0', 'work'), thought('a1', 'bet')],
      ),
    );
    expect(venueOf(frame, 'a0')).toBe('work');
    expect(venueOf(frame, 'a1')).toBe('casino');
  });

  it('reads the newest action per agent from a newest-first window', () => {
    const frame = buildFrameFromSnapshot(
      snapshot([agent('a0')], [thought('a0', 'bet', 9), thought('a0', 'work', 8)]),
    );
    expect(venueOf(frame, 'a0')).toBe('casino');
  });

  it('falls back to a stable home venue for an agent that has not acted', () => {
    const first = buildFrameFromSnapshot(snapshot([agent('a0'), agent('a1')]));
    const again = buildFrameFromSnapshot(snapshot([agent('a1'), agent('a0')]));
    expect(venueOf(first, 'a0')).toBe(venueOf(again, 'a0'));
    expect(venueOf(first, 'a1')).toBe(venueOf(again, 'a1'));
    expect(venueOf(first, 'a0')).not.toBe(venueOf(first, 'a1'));
  });

  it('sends a married pair to the same venue, chosen by the lower agent id', () => {
    const frame = buildFrameFromSnapshot(
      snapshot(
        [agent('a0', { spouse: 'a1' }), agent('a1', { spouse: 'a0' })],
        [thought('a0', 'work'), thought('a1', 'bet')],
      ),
    );
    expect(venueOf(frame, 'a1')).toBe(venueOf(frame, 'a0'));
    expect(venueOf(frame, 'a0')).toBe('work');
  });

  it('gives agents sharing a venue distinct positions', () => {
    const frame = buildFrameFromSnapshot(
      snapshot(
        [agent('a0'), agent('a1'), agent('a2')],
        [thought('a0', 'work'), thought('a1', 'work'), thought('a2', 'work')],
      ),
    );
    const seen = new Set(frame.agents.map((a) => a.position.join(',')));
    expect(seen.size).toBe(3);
  });

  it('carries the triple and leaves the verdict null — the judge runs offline', () => {
    const frame = buildFrameFromSnapshot(
      snapshot([agent('a0')], [thought('a0', 'work')]),
    );
    const a0 = frame.agents[0];
    expect(a0.monologue).toBe('a0 thinks');
    expect(a0.publicMessage).toBe('a0 says');
    expect(a0.outcome).toBe('ok');
    expect(a0.verdict).toBeNull();
  });

  it('is an empty frame, not a crash, without a snapshot', () => {
    expect(buildFrameFromSnapshot(null)).toEqual({ turn: 0, agents: [] });
  });

  it('drops eliminated agents', () => {
    const frame = buildFrameFromSnapshot(
      snapshot([agent('a0'), agent('a1', { alive: false })]),
    );
    expect(frame.agents.map((a) => a.agentId)).toEqual(['a0']);
  });
});

describe('buildFramesFromTurns', () => {
  const turns = [
    turnRecord(1, 'a0', 'work'),
    turnRecord(1, 'a1', 'bet'),
    turnRecord(2, 'a0', 'trade'),
    turnRecord(2, 'a1', 'work'),
  ];

  it('produces one frame per turn, in turn order', () => {
    const frames = buildFramesFromTurns(turns);
    expect(frames.map((f) => f.turn)).toEqual([1, 2]);
    expect(frames[0].agents.map((a) => a.agentId)).toEqual(['a0', 'a1']);
  });

  it('places from the trace by the same law as the live snapshot', () => {
    const fromTrace = buildFramesFromTurns([turnRecord(1, 'a0', 'work')])[0];
    const fromLive = buildFrameFromSnapshot(
      snapshot([agent('a0')], [thought('a0', 'work', 1)], 1),
    );
    expect(fromTrace.agents[0].venueId).toBe(fromLive.agents[0].venueId);
    expect(fromTrace.agents[0].position).toEqual(fromLive.agents[0].position);
  });

  it('honours the spouse-follow rule from trace state', () => {
    const frame = buildFramesFromTurns([
      turnRecord(1, 'a0', 'work', {
        state: { balance: 1, trust_score: 1, inventory: {}, alive: null, spouse_id: 'a1' },
      }),
      turnRecord(1, 'a1', 'bet', {
        state: { balance: 1, trust_score: 1, inventory: {}, alive: null, spouse_id: 'a0' },
      }),
    ])[0];
    expect(venueOf(frame, 'a1')).toBe(venueOf(frame, 'a0'));
  });

  it('attaches a verdict when one is supplied, and null when none is', () => {
    const verdict: Verdict = {
      turn: 1,
      agent_id: 'a0',
      is_deceptive: true,
      deception_type: 'misdirection',
      target_id: 'a1',
      confidence: 0.7,
      sophistication: 2,
    };
    const [frame] = buildFramesFromTurns(turns.slice(0, 2), [verdict]);
    expect(frame.agents.find((a) => a.agentId === 'a0')?.verdict).toEqual(verdict);
    expect(frame.agents.find((a) => a.agentId === 'a1')?.verdict).toBeNull();
  });

  it('gives an agent the same colour in every frame of a run', () => {
    const frames = buildFramesFromTurns(turns);
    const colourAt = (i: number, id: string) =>
      frames[i].agents.find((a) => a.agentId === id)?.color;
    expect(colourAt(0, 'a0')).toBe(colourAt(1, 'a0'));
    expect(colourAt(0, 'a0')).not.toBe(colourAt(0, 'a1'));
  });

  it('is empty for an empty trace', () => {
    expect(buildFramesFromTurns([])).toEqual([]);
  });
});
