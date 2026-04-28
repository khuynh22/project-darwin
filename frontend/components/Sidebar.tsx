'use client';

import type { WorldSnapshot } from '@/lib/ws';

export default function Sidebar({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const agents = snapshot?.agents ?? [];
  const totalAlive = agents.filter((a) => a.alive).reduce((sum, a) => sum + a.balance, 0);

  return (
    <aside className="bg-arena-panel border-l border-black/40 overflow-y-auto p-4 space-y-3">
      <h2 className="text-arena-accent text-xs tracking-widest mb-2">AGENTS</h2>
      {agents.map((a) => {
        const share = totalAlive > 0 && a.alive ? (a.balance / totalAlive) * 100 : 0;
        return (
          <div
            key={a.agent_id}
            className={`rounded border p-3 ${
              a.alive ? 'border-arena-accent/30 bg-black/30' : 'border-red-900 bg-black/60 opacity-50'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold">{a.display_name}</span>
              <span className="text-xs text-white/60">{a.provider}</span>
            </div>
            <div className="mt-1 text-lg">
              ${a.balance.toFixed(2)}{' '}
              <span className="text-xs text-white/60">({share.toFixed(0)}% share)</span>
            </div>
            <div className="text-xs text-white/70 mt-1">
              {a.spouse && <span className="mr-2">married→{a.spouse}</span>}
              {a.allies?.length > 0 && <span className="mr-2">allies: {a.allies.join(',')}</span>}
              {a.enemies?.length > 0 && <span className="text-red-300">enemies: {a.enemies.join(',')}</span>}
              {!a.alive && <span className="text-red-400">ELIMINATED</span>}
            </div>
          </div>
        );
      })}
    </aside>
  );
}
