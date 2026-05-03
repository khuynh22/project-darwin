'use client';

import type { WorldSnapshot } from '@/lib/ws';

const COLOR_HEX: Record<string, string> = {
  red: '#ef4444', blue: '#3b82f6', green: '#22c55e', purple: '#a855f7',
  orange: '#f97316', cyan: '#06b6d4', pink: '#ec4899', yellow: '#eab308',
  teal: '#14b8a6', indigo: '#6366f1',
};

function TrustBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color = pct >= 60 ? '#22c55e' : pct >= 35 ? '#eab308' : '#ef4444';
  return (
    <div className="flex items-center gap-1.5 mt-1">
      <span className="text-[10px] text-zinc-500 w-6">Trust:{Math.round(pct)}</span>
      <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export default function Sidebar({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const agents = snapshot?.agents ?? [];
  const totalAlive = agents.filter((a) => a.alive).reduce((sum, a) => sum + a.balance, 0);

  return (
    <aside className="bg-zinc-900/80 border-l border-zinc-800 overflow-y-auto p-3 space-y-1.5">
      <h2 className="text-zinc-400 text-[10px] tracking-widest font-medium uppercase mb-2">Agents</h2>
      {agents.map((a) => {
        const share = totalAlive > 0 && a.alive ? (a.balance / totalAlive) * 100 : 0;
        const inv = a.inventory || {};
        const dotColor = COLOR_HEX[a.sprite] || '#888';
        return (
          <div key={a.agent_id}
            className={`rounded-lg border p-2.5 transition-all ${a.alive ? 'border-zinc-800 bg-zinc-900/60 hover:border-zinc-700' : 'border-zinc-800/50 bg-zinc-950/60 opacity-40'
              }`}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: dotColor }} />
              <span className="text-sm font-medium text-zinc-200 flex-1">{a.display_name}</span>
              <span className="text-[10px] text-zinc-600 font-mono">{a.provider}</span>
            </div>

            {/* Balance */}
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-semibold text-white font-mono">${a.balance.toFixed(2)}</span>
              <span className="text-[10px] text-zinc-500">{share.toFixed(0)}%</span>
            </div>

            {/* Trust */}
            <TrustBar score={a.trust_score} />

            {/* Inventory */}
            {Object.values(inv).some(v => v > 0) && (
              <div className="flex gap-2 mt-1.5 text-[10px] text-zinc-400">
                {inv.ore > 0 && <span title="Ore">{inv.ore} ore</span>}
                {inv.food > 0 && <span title="Food">{inv.food} food</span>}
                {inv.tech > 0 && <span title="Tech">{inv.tech} tech</span>}
              </div>
            )}

            {/* Social */}
            <div className="text-[10px] text-zinc-500 mt-1 flex flex-wrap gap-x-2">
              {a.spouse && <span className="text-pink-400">married: {a.spouse}</span>}
              {a.allies?.length > 0 && <span>allies: {a.allies.join(', ')}</span>}
              {a.enemies?.length > 0 && <span className="text-red-400">enemies: {a.enemies.join(', ')}</span>}
            </div>

            {/* Badges */}
            {(a.steal_count > 0 || a.rest_bonus || a.will_target || !a.alive) && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {!a.alive && <span className="text-[9px] px-1.5 py-0.5 bg-red-950/80 text-red-400 rounded font-medium">ELIMINATED</span>}
                {a.steal_count > 0 && <span className="text-[9px] px-1.5 py-0.5 bg-red-950/50 text-red-300 rounded">{a.steal_count} steals</span>}
                {a.rest_bonus && <span className="text-[9px] px-1.5 py-0.5 bg-blue-950/50 text-blue-300 rounded">resting</span>}
                {a.will_target && <span className="text-[9px] px-1.5 py-0.5 bg-purple-950/50 text-purple-300 rounded">will: {a.will_target}</span>}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}
