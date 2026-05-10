'use client';

import {
  Cpu,
  Heart,
  Mountain,
  ShieldAlert,
  Skull,
  Wheat,
} from 'lucide-react';
import type { WorldSnapshot } from '@/lib/ws';
import AgentSigil from './AgentSigil';
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

function TrustBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color = pct >= 60 ? '#22c55e' : pct >= 35 ? '#eab308' : '#ef4444';
  return (
    <div className="flex items-center gap-1.5 mt-1">
      <span className="text-[10px] text-zinc-500 tabular-nums w-10">
        Trust {Math.round(pct)}
      </span>
      <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

interface SidebarProps {
  snapshot: WorldSnapshot | null;
  running?: boolean;
}

export default function Sidebar({ snapshot, running = false }: SidebarProps) {
  const agents = snapshot?.agents ?? [];
  const totalAlive = agents
    .filter((a) => a.alive)
    .reduce((sum, a) => sum + a.balance, 0);

  return (
    <aside className="bg-zinc-900/70 border-l border-zinc-800 overflow-y-auto p-3 space-y-2 w-72 flex-shrink-0">
      <div className="flex items-baseline justify-between mb-1">
        <h2 className="text-zinc-400 text-[10px] tracking-widest font-medium uppercase">
          Agents
        </h2>
        <span className="text-zinc-600 text-[10px] font-mono">
          {agents.filter((a) => a.alive).length}/{agents.length}
        </span>
      </div>

      {agents.map((a) => {
        const share = totalAlive > 0 && a.alive ? (a.balance / totalAlive) * 100 : 0;
        const inv = a.inventory || {};
        const dotColor = COLOR_HEX[a.sprite] || '#888';
        const sigilState = !a.alive ? 'idle' : running ? 'thinking' : 'idle';
        return (
          <div
            key={a.agent_id}
            className={cn(
              'rounded-lg border p-2.5 transition-all',
              a.alive
                ? 'border-zinc-800 bg-zinc-900/60 hover:border-zinc-700'
                : 'border-zinc-800/50 bg-zinc-950/60 opacity-50',
            )}
          >
            {/* Header with mini-sigil */}
            <div className="flex items-center gap-2 mb-1.5">
              <div className="flex-shrink-0">
                <AgentSigil
                  color={dotColor}
                  size={32}
                  state={sigilState}
                  alive={a.alive}
                />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-semibold text-zinc-100 truncate">
                    {a.display_name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                  <span className="font-mono">{a.provider}</span>
                  <span>•</span>
                  <span className="capitalize">{a.specialty}</span>
                </div>
              </div>
            </div>

            {/* Balance */}
            <div className="flex items-baseline gap-1.5">
              <span className="text-base font-semibold text-zinc-100 font-mono">
                ${a.balance.toFixed(2)}
              </span>
              {a.invested > 0 && (
                <span
                  className="text-[10px] text-blue-400 font-mono"
                  title="Locked in investments/loans"
                >
                  +${a.invested.toFixed(2)} inv
                </span>
              )}
              <span className="text-[10px] text-zinc-500 ml-auto tabular-nums">
                {share.toFixed(0)}%
              </span>
            </div>

            <TrustBar score={a.trust_score} />

            {/* Inventory icons */}
            {(inv.ore > 0 || inv.food > 0 || inv.tech > 0) && (
              <div className="flex items-center gap-2 mt-1.5 text-[10px] text-zinc-400">
                {inv.ore > 0 && (
                  <span className="flex items-center gap-1" title="Ore: +$0.02/turn work bonus">
                    <Mountain size={10} className="text-amber-400/80" />
                    {inv.ore}
                  </span>
                )}
                {inv.food > 0 && (
                  <span className="flex items-center gap-1" title="Food: consumed at tax time or $1 penalty">
                    <Wheat size={10} className="text-yellow-400/80" />
                    {inv.food}
                  </span>
                )}
                {inv.tech > 0 && (
                  <span className="flex items-center gap-1" title="Tech: -5% tax per unit">
                    <Cpu size={10} className="text-cyan-400/80" />
                    {inv.tech}
                  </span>
                )}
              </div>
            )}

            {/* Social */}
            {(a.spouse || a.allies?.length > 0 || a.enemies?.length > 0) && (
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
                {a.spouse && (
                  <span className="flex items-center gap-1 text-pink-400">
                    <Heart size={9} fill="currentColor" /> {a.spouse}
                  </span>
                )}
                {a.allies?.length > 0 && (
                  <span className="text-emerald-400/90">allies: {a.allies.join(', ')}</span>
                )}
                {a.enemies?.length > 0 && (
                  <span className="text-red-400/90">enemies: {a.enemies.join(', ')}</span>
                )}
              </div>
            )}

            {/* Badges */}
            {(a.steal_count > 0 || a.rest_bonus || a.will_target || !a.alive) && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {!a.alive && (
                  <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 bg-red-950/80 text-red-300 rounded font-medium">
                    <Skull size={10} /> ELIMINATED
                  </span>
                )}
                {a.steal_count > 0 && (
                  <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 bg-red-950/50 text-red-200 rounded">
                    <ShieldAlert size={9} /> {a.steal_count}
                  </span>
                )}
                {a.rest_bonus && (
                  <span className="text-[9px] px-1.5 py-0.5 bg-blue-950/50 text-blue-200 rounded">
                    resting
                  </span>
                )}
                {a.will_target && (
                  <span className="text-[9px] px-1.5 py-0.5 bg-purple-950/50 text-purple-200 rounded">
                    will → {a.will_target}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}
