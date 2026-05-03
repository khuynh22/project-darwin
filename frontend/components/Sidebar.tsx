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
            className={`rounded border p-3 ${a.alive ? 'border-arena-accent/30 bg-black/30' : 'border-red-900 bg-black/60 opacity-50'
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
              {a.spouse && <span className="mr-2">married-&gt;{a.spouse}</span>}
              {a.allies?.length > 0 && <span className="mr-2">allies: {a.allies.join(',')}</span>}
              {a.enemies?.length > 0 && <span className="text-red-300">enemies: {a.enemies.join(',')}</span>}
              {!a.alive && <span className="text-red-400">ELIMINATED</span>}
            </div>
            {a.consecutive_errors > 0 && a.alive && (
              <div className="mt-1 text-xs px-2 py-1 bg-yellow-900/40 border border-yellow-600/50 rounded">
                <span className="text-yellow-400">ERRORS: {a.consecutive_errors}</span>
                {a.last_error && <span className="text-yellow-300/60 ml-1 truncate block">{a.last_error.slice(0, 80)}</span>}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}
