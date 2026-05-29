'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { AgentSnap, WorldSnapshot } from '@/lib/ws';
import Critter, { type Bubble, type CritterState } from './Critter';
import {
  ACTIONS,
  COLOR_HEX,
  FAMILIES,
  HOME_VENUES,
  STAGE_H,
  STAGE_W,
  VENUES,
  VENUES_BY_ID,
  venueSlot,
} from '@/lib/town';

interface TownProps {
  snapshot: WorldSnapshot | null;
  running?: boolean;
}

interface AgentPlacement {
  venueId: string;
  pos: { x: number; y: number };
  actionId: string | undefined;
}

const EMPTY_AGENTS: AgentSnap[] = [];
const EMPTY_THOUGHTS: WorldSnapshot['recent_thoughts'] = [];

export default function Town({ snapshot, running = false }: TownProps) {
  const agents = snapshot?.agents ?? EMPTY_AGENTS;
  const thoughts = snapshot?.recent_thoughts ?? EMPTY_THOUGHTS;
  const turn = snapshot?.turn ?? 0;

  // Latest action per agent — `recent_thoughts` is newest-first.
  const latestActions = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of thoughts) {
      if (!map.has(t.agent_id)) map.set(t.agent_id, t.action);
    }
    return map;
  }, [thoughts]);

  // Assign each agent to a venue slot. Stable order keeps slots consistent
  // across renders so critters don't jitter between adjacent positions.
  const placements = useMemo(() => {
    const sortedAgents = [...agents].sort((a, b) => a.agent_id.localeCompare(b.agent_id));
    const groups: Record<string, AgentSnap[]> = {};
    for (const v of VENUES) groups[v.id] = [];

    const venueIdForAgent = (agent: AgentSnap, fallbackIdx: number): string => {
      const action = latestActions.get(agent.agent_id);
      const def = action ? ACTIONS[action] : undefined;
      return def?.venue ?? HOME_VENUES[fallbackIdx % HOME_VENUES.length];
    };

    for (let i = 0; i < sortedAgents.length; i++) {
      const agent = sortedAgents[i];
      let venueId = venueIdForAgent(agent, i);
      // Spouse-follow: the lower agent_id picks the venue, the partner mirrors.
      if (agent.spouse) {
        const spouse = sortedAgents.find((x) => x.agent_id === agent.spouse);
        if (spouse) {
          const spouseIdx = sortedAgents.indexOf(spouse);
          const spouseVenue = venueIdForAgent(spouse, spouseIdx);
          venueId = agent.agent_id < agent.spouse ? venueId : spouseVenue;
        }
      }
      groups[venueId].push(agent);
    }

    const map = new Map<string, AgentPlacement>();
    for (const venue of VENUES) {
      const list = groups[venue.id];
      list.forEach((a, idx) => {
        map.set(a.agent_id, {
          venueId: venue.id,
          pos: venueSlot(venue, idx),
          actionId: latestActions.get(a.agent_id),
        });
      });
    }
    return map;
  }, [agents, latestActions]);

  // Facing direction tracker — flip on horizontal travel.
  const prevPosRef = useRef<Record<string, { x: number; y: number }>>({});
  const [facings, setFacings] = useState<Record<string, 1 | -1>>({});
  useEffect(() => {
    let changed = false;
    const next: Record<string, 1 | -1> = { ...facings };
    for (const agent of agents) {
      const p = placements.get(agent.agent_id);
      if (!p) continue;
      const prev = prevPosRef.current[agent.agent_id];
      if (prev) {
        const dx = p.pos.x - prev.x;
        if (Math.abs(dx) > 2) {
          const dir: 1 | -1 = dx > 0 ? 1 : -1;
          if (next[agent.agent_id] !== dir) {
            next[agent.agent_id] = dir;
            changed = true;
          }
        }
      }
      prevPosRef.current[agent.agent_id] = p.pos;
    }
    if (changed) setFacings(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placements, agents]);

  // Brief "thinking" pulse at the start of each turn — dots bubble.
  const [thinkingPulse, setThinkingPulse] = useState(false);
  const lastTurnRef = useRef<number>(-1);
  useEffect(() => {
    if (turn === lastTurnRef.current) return;
    lastTurnRef.current = turn;
    if (turn === 0) return;
    setThinkingPulse(true);
    const id = setTimeout(() => setThinkingPulse(false), 1100);
    return () => clearTimeout(id);
  }, [turn]);

  if (agents.length === 0) {
    return (
      <div className="town-card relative bg-[#FFF3DC] border-[1.5px] border-cozy-card-edge rounded-3xl shadow-cozy-md overflow-hidden flex items-center justify-center min-h-[560px]">
        <div className="text-center px-6 py-8 max-w-sm">
          <div className="text-3xl mb-2">🌱</div>
          <h3 className="text-lg font-display text-cozy-ink mb-1">The town is quiet</h3>
          <p className="text-xs text-cozy-ink-soft">
            Open the config panel to seed 3–10 critters and start a new run.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="relative bg-[#FFF3DC] border-[1.5px] border-cozy-card-edge rounded-3xl shadow-cozy-md overflow-hidden"
      style={{ minHeight: STAGE_H }}
    >
      {/* Soft dot texture overlay */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(184,124,72,0.06) 1px, transparent 1.4px)',
          backgroundSize: '20px 20px',
          opacity: 0.55,
        }}
      />

      <div
        className="relative mx-auto"
        style={{ width: STAGE_W, height: STAGE_H }}
      >
        {/* Decorative dashed paths from plaza to each venue */}
        <svg
          width={STAGE_W}
          height={STAGE_H}
          className="absolute inset-0 pointer-events-none"
          aria-hidden
        >
          {VENUES.map((v) => (
            <line
              key={v.id}
              x1={STAGE_W / 2}
              y1={STAGE_H / 2}
              x2={v.x}
              y2={v.y + 30}
              stroke="rgba(184,124,72,0.16)"
              strokeWidth={12}
              strokeLinecap="round"
              strokeDasharray="2 12"
            />
          ))}
        </svg>

        {/* Venue houses */}
        {VENUES.map((v) => (
          <VenueHouse key={v.id} venue={v} />
        ))}

        {/* Center plaza */}
        <TownSquare turn={turn} running={running} />

        {/* Critter layer */}
        {agents.map((agent) => {
          const p = placements.get(agent.agent_id);
          if (!p) return null;
          const color = COLOR_HEX[agent.sprite] || '#FFCBA0';
          const def = p.actionId ? ACTIONS[p.actionId] : undefined;
          const family = def ? FAMILIES[def.family] : undefined;
          let state: CritterState = 'idle';
          let bubble: Bubble | null = null;
          if (agent.alive) {
            if (thinkingPulse) {
              state = 'thinking';
              bubble = { kind: 'dots' };
            } else if (running) {
              state = 'thinking';
              bubble = { kind: 'dots' };
            } else if (def) {
              state = 'acting';
              bubble = {
                kind: 'intent',
                emoji: def.emoji,
                text: def.intent,
                tint: family?.color,
              };
            }
          }
          return (
            <Critter
              key={agent.agent_id}
              agentId={agent.agent_id}
              color={color}
              name={agent.display_name}
              balance={agent.balance}
              alive={agent.alive}
              state={state}
              bubble={bubble}
              target={p.pos}
              facing={facings[agent.agent_id] ?? 1}
            />
          );
        })}
      </div>
    </div>
  );
}

function VenueHouse({ venue }: { venue: (typeof VENUES)[number] }) {
  return (
    <div
      className="absolute text-center group"
      style={{ left: venue.x, top: venue.y, width: 120, transform: 'translate(-50%, -50%)' }}
    >
      <div
        className="relative mx-auto mt-[18px] grid place-items-center"
        style={{
          width: 84,
          height: 64,
          borderRadius: '12px 12px 14px 14px',
          background: venue.body,
          boxShadow: '0 4px 0 rgba(74,58,46,0.08), 0 10px 20px rgba(74,58,46,0.10)',
          fontSize: 28,
          transition: 'transform 0.25s cubic-bezier(0.4,1.4,0.5,1)',
        }}
      >
        {/* Pitched roof — CSS-border triangle */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '50px solid transparent',
            borderRight: '50px solid transparent',
            borderBottom: `22px solid ${venue.roof}`,
            marginBottom: -1,
            filter: 'drop-shadow(0 2px 0 rgba(74,58,46,0.08))',
          }}
        />
        {/* Window */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            width: 12,
            height: 12,
            borderRadius: 3,
            background: 'rgba(255,255,255,0.7)',
            boxShadow: 'inset 0 -2px 0 rgba(74,58,46,0.08)',
          }}
        />
        <span className="relative z-[1] leading-none">{venue.icon}</span>
      </div>
      <div className="mt-[10px] font-display font-semibold text-[13px] text-cozy-ink">
        {venue.label}
      </div>
      <div className="mt-[2px] text-[9px] uppercase font-bold text-cozy-ink-soft tracking-[0.12em]">
        {venue.sub}
      </div>
    </div>
  );
}

function TownSquare({ turn, running }: { turn: number; running: boolean }) {
  return (
    <div
      className="absolute left-1/2 top-1/2 grid place-items-center text-center"
      style={{
        width: 160,
        height: 160,
        transform: 'translate(-50%, -50%)',
        borderRadius: '50%',
        background: '#FFE6BF',
        border: '2px solid #F2D9A6',
        boxShadow:
          'inset 0 0 0 5px #FFF3DA, inset 0 0 0 6px #F2D9A6, 0 6px 18px rgba(184,124,72,0.16)',
      }}
    >
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 16,
          borderRadius: '50%',
          border: '1.5px dashed rgba(184,124,72,0.35)',
          pointerEvents: 'none',
        }}
      />
      <div>
        <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-cozy-ink-soft mb-1">
          Turn
        </div>
        <div
          className="font-display font-semibold text-[50px] text-cozy-ink leading-[0.9] animate-ts-pulse"
          style={{ textShadow: '0 2px 0 rgba(184,124,72,0.18)' }}
        >
          {String(turn).padStart(2, '0')}
        </div>
        <div className="text-[9px] uppercase tracking-[0.1em] font-bold text-cozy-ink-soft mt-[2px]">
          {running ? 'thinking…' : 'Project Darwin'}
        </div>
      </div>
    </div>
  );
}
