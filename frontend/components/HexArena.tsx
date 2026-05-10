'use client';

import { motion } from 'framer-motion';
import {
  Dice5,
  Hammer,
  Landmark,
  MessageCircle,
  ShoppingBag,
  Swords,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type ComponentType } from 'react';
import type { AgentSnap, WorldSnapshot } from '@/lib/ws';
import AgentSigil, { type SigilState } from './AgentSigil';
import { cn } from '@/lib/utils';

const COLOR_HEX: Record<string, string> = {
  red: '#ef4444',
  blue: '#3b82f6',
  green: '#22c55e',
  purple: '#a855f7',
  orange: '#f97316',
  cyan: '#06b6d4',
  pink: '#ec4899',
  yellow: '#eab308',
  teal: '#14b8a6',
  indigo: '#6366f1',
};

const ACTION_VENUE: Record<string, string> = {
  work: 'workplace',
  trade: 'marketplace',
  bet: 'casino',
  socialize: 'lounge',
  sabotage: 'alley',
  invest: 'bank',
  steal: 'alley',
  lend: 'marketplace',
  charity: 'marketplace',
  propose_deal: 'lounge',
  skip: 'workplace',
  slander: 'alley',
  vouch: 'lounge',
  gift: 'marketplace',
  bluff: 'lounge',
  extort: 'alley',
  strike: 'workplace',
  rest: 'lounge',
  will: 'bank',
  gaslight: 'alley',
  bribe: 'marketplace',
};

const ACTION_LABELS: Record<string, string> = {
  work: 'Working',
  trade: 'Trading',
  bet: 'Betting',
  socialize: 'Socializing',
  sabotage: 'Sabotaging',
  invest: 'Investing',
  steal: 'Stealing',
  lend: 'Lending',
  charity: 'Donating',
  propose_deal: 'Dealing',
  slander: 'Slandering',
  vouch: 'Vouching',
  gift: 'Gifting',
  bluff: 'Bluffing',
  extort: 'Extorting',
  strike: 'Striking',
  rest: 'Resting',
  will: 'Writing will',
  gaslight: 'Gaslighting',
  bribe: 'Bribing',
  skip: 'Idle',
};

type Venue = {
  id: string;
  label: string;
  desc: string;
  Icon: ComponentType<{ className?: string; size?: number }>;
  color: string;
  x: number; // % center
  y: number; // % center
};

// Hexagonal arrangement around a central point.
const VENUES: Venue[] = [
  { id: 'workplace', label: 'Work', desc: 'Labor & production', Icon: Hammer, color: '#3b82f6', x: 50, y: 11 },
  { id: 'casino', label: 'Casino', desc: 'Gambling', Icon: Dice5, color: '#ef4444', x: 86, y: 30 },
  { id: 'alley', label: 'Alley', desc: 'Steal, sabotage', Icon: Swords, color: '#a1a1aa', x: 86, y: 70 },
  { id: 'lounge', label: 'Lounge', desc: 'Social & deals', Icon: MessageCircle, color: '#a855f7', x: 50, y: 89 },
  { id: 'marketplace', label: 'Market', desc: 'Trade, lend, gift', Icon: ShoppingBag, color: '#22c55e', x: 14, y: 70 },
  { id: 'bank', label: 'Bank', desc: 'Investments & wills', Icon: Landmark, color: '#eab308', x: 14, y: 30 },
];

const VENUES_BY_ID: Record<string, Venue> = Object.fromEntries(VENUES.map((v) => [v.id, v]));

const WALK_MS = 3500;
const VENUE_FLASH_MS = 1100;

// Cluster offset within a venue: arrange agents in a small grid below the venue label.
function clusterOffset(index: number, count: number): { dx: number; dy: number } {
  if (count <= 1) return { dx: 0, dy: 9 };
  const cols = count <= 3 ? count : 3;
  const col = index % cols;
  const row = Math.floor(index / cols);
  const dx = (col - (cols - 1) / 2) * 9;
  const dy = 9 + row * 8.5;
  return { dx, dy };
}

interface HexArenaProps {
  snapshot: WorldSnapshot | null;
  running?: boolean;
}

const EMPTY_AGENTS: AgentSnap[] = [];
const EMPTY_THOUGHTS: WorldSnapshot['recent_thoughts'] = [];

export default function HexArena({ snapshot, running = false }: HexArenaProps) {
  const agents = snapshot?.agents ?? EMPTY_AGENTS;
  const thoughts = snapshot?.recent_thoughts ?? EMPTY_THOUGHTS;
  const turn = snapshot?.turn ?? 0;

  // Latest action per agent (most recent thought wins).
  const latestActions = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of thoughts) {
      if (!map.has(t.agent_id)) map.set(t.agent_id, t.action);
    }
    return map;
  }, [thoughts]);

  // Group agents by venue (with spouse-follow rule).
  const venueGroups = useMemo(() => {
    const groups: Record<string, AgentSnap[]> = {};
    for (const v of VENUES) groups[v.id] = [];
    for (const agent of agents) {
      if (!agent.alive) continue;
      const action = latestActions.get(agent.agent_id) || 'work';
      let venueId = ACTION_VENUE[action] || 'workplace';
      // Spouse follow: lower agent_id picks the venue, partner mirrors.
      if (agent.spouse) {
        const spouseAction = latestActions.get(agent.spouse) || 'work';
        const spouseVenue = ACTION_VENUE[spouseAction] || 'workplace';
        venueId = agent.agent_id < agent.spouse ? venueId : spouseVenue;
      }
      if (!groups[venueId]) groups[venueId] = [];
      groups[venueId].push(agent);
    }
    return groups;
  }, [agents, latestActions]);

  // Per-agent target venue + index within venue.
  const targets = useMemo(() => {
    const map = new Map<string, { venueId: string; clusterIndex: number; clusterCount: number }>();
    for (const venue of VENUES) {
      const list = venueGroups[venue.id] || [];
      list.forEach((a, i) => {
        map.set(a.agent_id, { venueId: venue.id, clusterIndex: i, clusterCount: list.length });
      });
    }
    return map;
  }, [venueGroups]);

  // Track which agents are currently "walking" (just changed venue).
  const prevVenueRef = useRef<Record<string, string>>({});
  const [walkingAgents, setWalkingAgents] = useState<Set<string>>(new Set());

  useEffect(() => {
    const movers = new Set<string>();
    for (const agent of agents) {
      if (!agent.alive) continue;
      const target = targets.get(agent.agent_id);
      if (!target) continue;
      const prev = prevVenueRef.current[agent.agent_id];
      if (prev && prev !== target.venueId) movers.add(agent.agent_id);
      prevVenueRef.current[agent.agent_id] = target.venueId;
    }
    if (movers.size > 0) {
      setWalkingAgents(movers);
      const t = setTimeout(() => setWalkingAgents(new Set()), WALK_MS);
      return () => clearTimeout(t);
    }
    // No movement: clear if there were stale walkers (defensive).
    return undefined;
  }, [agents, targets]);

  // Track venues that just had action (for a brief flash).
  const [flashedVenues, setFlashedVenues] = useState<Set<string>>(new Set());
  const lastTurnRef = useRef<number>(-1);
  useEffect(() => {
    if (turn === lastTurnRef.current) return;
    lastTurnRef.current = turn;
    const venues = new Set<string>();
    for (const t of thoughts) {
      if (t.turn !== turn) continue;
      const venueId = ACTION_VENUE[t.action];
      if (venueId) venues.add(venueId);
    }
    if (venues.size > 0) {
      setFlashedVenues(venues);
      const id = setTimeout(() => setFlashedVenues(new Set()), VENUE_FLASH_MS);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [turn, thoughts]);

  if (agents.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm bg-zinc-950">
        <div className="text-center">
          <p className="text-zinc-400 mb-1">No agents configured</p>
          <p className="text-xs text-zinc-600">Open Config to set up the simulation</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 relative overflow-hidden bg-gradient-to-b from-zinc-950 via-zinc-950 to-black">
      {/* Background dot grid */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            'radial-gradient(circle, #71717a 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      {/* Hex connection skeleton (faint) */}
      <svg
        aria-hidden
        className="absolute inset-0 w-full h-full pointer-events-none"
        preserveAspectRatio="none"
        viewBox="0 0 100 100"
      >
        <polygon
          points={VENUES.map((v) => `${v.x},${v.y}`).join(' ')}
          fill="none"
          stroke="#27272a"
          strokeWidth={0.15}
          strokeDasharray="0.6 0.4"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      {/* Center core decoration */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
        <motion.div
          className="rounded-full border border-zinc-800/80"
          style={{ width: 120, height: 120 }}
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
        >
          <div className="w-full h-full rounded-full border border-dashed border-zinc-800/50" />
        </motion.div>
        <div className="absolute inset-0 flex items-center justify-center text-[9px] uppercase tracking-[0.25em] text-zinc-700">
          turn {turn}
        </div>
      </div>

      {/* Venue zones */}
      {VENUES.map((venue) => {
        const flashed = flashedVenues.has(venue.id);
        const count = (venueGroups[venue.id] || []).length;
        return (
          <VenueZone key={venue.id} venue={venue} flashed={flashed} count={count} />
        );
      })}

      {/* Agents (absolute, animated between venues) */}
      {agents.map((agent) => {
        if (!agent.alive) return null;
        const target = targets.get(agent.agent_id);
        if (!target) return null;
        const venue = VENUES_BY_ID[target.venueId];
        const cluster = clusterOffset(target.clusterIndex, target.clusterCount);
        const x = venue.x + cluster.dx;
        const y = venue.y + cluster.dy;
        const isWalking = walkingAgents.has(agent.agent_id);
        const sigilState: SigilState = isWalking ? 'walking' : running ? 'thinking' : 'idle';
        const action = latestActions.get(agent.agent_id);
        return (
          <AgentMarker
            key={agent.agent_id}
            agent={agent}
            x={x}
            y={y}
            sigilState={sigilState}
            actionLabel={action ? ACTION_LABELS[action] : undefined}
          />
        );
      })}
    </div>
  );
}

interface VenueZoneProps {
  venue: Venue;
  flashed: boolean;
  count: number;
}

function VenueZone({ venue, flashed, count }: VenueZoneProps) {
  const { Icon, label, desc, color, x, y } = venue;
  return (
    <div
      className="absolute pointer-events-none"
      style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}
    >
      {/* Venue glow backdrop */}
      <motion.div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          width: 200,
          height: 160,
          background: `radial-gradient(ellipse at center, ${color}18 0%, ${color}00 70%)`,
        }}
        animate={flashed ? { scale: [1, 1.08, 1], opacity: [0.8, 1.2, 0.8] } : { scale: 1, opacity: 1 }}
        transition={{ duration: 0.9, ease: 'easeOut' }}
      />

      {/* Venue label */}
      <div
        className={cn(
          'relative flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg',
          'bg-zinc-900/70 backdrop-blur-sm border transition-colors',
          flashed ? 'border-zinc-600' : 'border-zinc-800/80',
        )}
      >
        <div className="flex items-center gap-1.5">
          <Icon size={12} className="text-zinc-300" />
          <span className="text-[11px] font-semibold tracking-wide text-zinc-200 uppercase">
            {label}
          </span>
          {count > 0 && (
            <span className="text-[9px] font-mono px-1 rounded bg-zinc-800 text-zinc-400">
              {count}
            </span>
          )}
        </div>
        <span className="text-[9px] text-zinc-500">{desc}</span>
      </div>
    </div>
  );
}

interface AgentMarkerProps {
  agent: AgentSnap;
  x: number;
  y: number;
  sigilState: SigilState;
  actionLabel?: string;
}

function AgentMarker({ agent, x, y, sigilState, actionLabel }: AgentMarkerProps) {
  const color = COLOR_HEX[agent.sprite] || '#888';
  const isWalking = sigilState === 'walking';
  return (
    <motion.div
      className="absolute z-20 pointer-events-auto"
      style={{ left: 0, top: 0 }}
      initial={false}
      animate={{ left: `${x}%`, top: `${y}%` }}
      // Mostly-linear easing so motion is visible the whole trip,
      // not bunched into the middle (which reads as "instant").
      transition={{ duration: WALK_MS / 1000, ease: [0.45, 0.05, 0.55, 0.95] }}
    >
      {/* Bobbing wrapper — gentle vertical sway during travel implies steps. */}
      <motion.div
        className="relative -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
        animate={
          isWalking
            ? { y: [0, -3, 0, -3, 0, -2, 0], scale: [1, 1.04, 1, 1.04, 1, 1.02, 1] }
            : { y: 0, scale: 1 }
        }
        transition={
          isWalking
            ? { duration: WALK_MS / 1000, ease: 'linear' }
            : { duration: 0.3 }
        }
        title={`${agent.display_name} • ${agent.provider} • $${agent.balance.toFixed(2)} • Trust ${agent.trust_score}`}
      >
        <AgentSigil color={color} size={56} state={sigilState} alive={agent.alive} />
        <div className="mt-0.5 flex flex-col items-center min-w-[64px]">
          <span className="text-[10px] font-semibold text-zinc-200 leading-tight whitespace-nowrap">
            {agent.display_name}
          </span>
          <span className="text-[9px] font-mono text-zinc-400">
            ${agent.balance.toFixed(2)}
          </span>
          {actionLabel && (
            <span
              className="text-[9px] italic px-1.5 rounded mt-0.5"
              style={{ color, backgroundColor: `${color}22` }}
            >
              {actionLabel}
            </span>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
