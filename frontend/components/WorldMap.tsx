'use client';

import type { WorldSnapshot, AgentSnap, ThoughtSnap } from '@/lib/ws';
import { useMemo } from 'react';

const COLOR_HEX: Record<string, string> = {
  red: '#ef4444', blue: '#3b82f6', green: '#22c55e', purple: '#a855f7',
  orange: '#f97316', cyan: '#06b6d4', pink: '#ec4899', yellow: '#eab308',
  teal: '#14b8a6', indigo: '#6366f1',
};

const ACTION_VENUE: Record<string, string> = {
  work: 'workplace', trade: 'marketplace', bet: 'casino',
  socialize: 'lounge', sabotage: 'alley', invest: 'bank',
  steal: 'alley', lend: 'marketplace', charity: 'marketplace',
  propose_deal: 'lounge', skip: 'workplace',
  slander: 'alley', vouch: 'lounge', gift: 'marketplace',
  bluff: 'lounge', extort: 'alley', strike: 'workplace',
  rest: 'lounge', will: 'bank', gaslight: 'alley', bribe: 'marketplace',
};

type VenueInfo = {
  id: string;
  label: string;
  icon: string;
  color: string;
  desc: string;
};

const VENUES: VenueInfo[] = [
  { id: 'workplace', label: 'Work', icon: '\u{1F3ED}', color: '#3b82f6', desc: 'Labor & production' },
  { id: 'bank', label: 'Bank', icon: '\u{1F3E6}', color: '#eab308', desc: 'Investments & wills' },
  { id: 'casino', label: 'Casino', icon: '\u{1F3B2}', color: '#ef4444', desc: 'Gambling' },
  { id: 'marketplace', label: 'Market', icon: '\u{1F4B1}', color: '#22c55e', desc: 'Trade, lend, gift' },
  { id: 'lounge', label: 'Lounge', icon: '\u{1F4AC}', color: '#a855f7', desc: 'Social & deals' },
  { id: 'alley', label: 'Alley', icon: '\u{26A0}', color: '#6b7280', desc: 'Steal, sabotage, extort' },
];

const ACTION_LABELS: Record<string, string> = {
  work: 'Working', trade: 'Trading', bet: 'Betting', socialize: 'Socializing',
  sabotage: 'Sabotaging', invest: 'Investing', steal: 'Stealing', lend: 'Lending',
  charity: 'Donating', propose_deal: 'Dealing', slander: 'Slandering',
  vouch: 'Vouching', gift: 'Gifting', bluff: 'Bluffing', extort: 'Extorting',
  strike: 'Striking', rest: 'Resting', will: 'Writing will', gaslight: 'Gaslighting',
  bribe: 'Bribing',
};

function AgentChip({ agent, latestAction }: { agent: AgentSnap; latestAction?: string }) {
  const color = COLOR_HEX[agent.sprite] || '#888';
  if (!agent.alive) return null;

  const initials = agent.display_name.slice(0, 2).toUpperCase();
  const actionLabel = ACTION_LABELS[latestAction || ''] || '';

  return (
    <div
      className="flex items-center gap-2 rounded-lg bg-zinc-800/60 border border-zinc-700/40 px-2.5 py-1.5 transition-all duration-300 hover:border-zinc-600/60 hover:bg-zinc-800/80"
      title={`${agent.display_name} (${agent.provider}) | Trust: ${agent.trust_score} | Steals: ${agent.steal_count}`}
    >
      {/* Avatar with initials */}
      <div
        className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
        style={{ backgroundColor: color }}
      >
        {initials}
      </div>
      {/* Info */}
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-zinc-200 truncate">{agent.display_name}</span>
          <span className="text-[9px] text-zinc-600 font-mono">{agent.provider}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-mono font-semibold text-zinc-300">${agent.balance.toFixed(2)}</span>
          {actionLabel && <span className="text-[9px] text-zinc-500 italic">{actionLabel}</span>}
        </div>
      </div>
    </div>
  );
}

export default function WorldMap({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const agents = snapshot?.agents ?? [];
  const thoughts = snapshot?.recent_thoughts ?? [];

  // Build latest action map
  const latestActions = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of thoughts) {
      if (!map.has(t.agent_id)) map.set(t.agent_id, t.action);
    }
    return map;
  }, [thoughts]);

  // Group agents by venue
  const venueGroups = useMemo(() => {
    const groups: Record<string, AgentSnap[]> = {};
    for (const v of VENUES) groups[v.id] = [];
    for (const agent of agents) {
      if (!agent.alive) continue;
      const action = latestActions.get(agent.agent_id) || 'work';
      let venue = ACTION_VENUE[action] || 'workplace';
      // Married agents follow spouse
      if (agent.spouse) {
        const spouseAction = latestActions.get(agent.spouse) || 'work';
        const spouseVenue = ACTION_VENUE[spouseAction] || 'workplace';
        venue = agent.agent_id < agent.spouse ? venue : spouseVenue;
      }
      if (!groups[venue]) groups[venue] = [];
      groups[venue].push(agent);
    }
    return groups;
  }, [agents, latestActions]);

  if (agents.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm">
        Configure agents to begin the simulation
      </div>
    );
  }

  return (
    <div className="flex-1 p-4 overflow-auto">
      <div className="grid grid-cols-3 gap-3 h-full">
        {VENUES.map((venue) => {
          const agentsHere = venueGroups[venue.id] || [];
          return (
            <div
              key={venue.id}
              className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-3 flex flex-col transition-all hover:border-zinc-700/60"
              style={{ borderLeftColor: venue.color + '30', borderLeftWidth: '3px' }}
            >
              {/* Venue header */}
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{venue.icon}</span>
                <div>
                  <h3 className="text-xs font-semibold text-zinc-300">{venue.label}</h3>
                  <p className="text-[9px] text-zinc-600">{venue.desc}</p>
                </div>
                {agentsHere.length > 0 && (
                  <span className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                    {agentsHere.length}
                  </span>
                )}
              </div>

              {/* Agents in this venue */}
              <div className="flex-1 flex flex-wrap items-start gap-2 content-start min-h-[40px]">
                {agentsHere.map((agent) => (
                  <AgentChip key={agent.agent_id} agent={agent} latestAction={latestActions.get(agent.agent_id)} />
                ))}
                {agentsHere.length === 0 && (
                  <span className="text-[10px] text-zinc-700 italic">empty</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
