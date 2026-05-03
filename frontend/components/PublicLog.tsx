'use client';

import type { WorldSnapshot } from '@/lib/ws';

const ACTION_COLORS: Record<string, string> = {
  steal: 'text-red-400', sabotage: 'text-red-400', extort: 'text-red-400',
  slander: 'text-orange-400', gaslight: 'text-orange-400', bluff: 'text-amber-300',
  charity: 'text-emerald-400', gift: 'text-emerald-400', vouch: 'text-emerald-400', lend: 'text-emerald-300',
  trade: 'text-blue-300', invest: 'text-blue-400', bribe: 'text-purple-400',
  socialize: 'text-cyan-300', propose_deal: 'text-cyan-300',
  work: 'text-zinc-500', bet: 'text-amber-400', rest: 'text-zinc-600',
  strike: 'text-orange-300', will: 'text-zinc-400',
};

export default function PublicLog({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const thoughts = snapshot?.recent_thoughts ?? [];

  return (
    <section className="flex-1 bg-zinc-900/60 border-r border-zinc-800 overflow-y-auto p-3 text-xs">
      <h2 className="text-zinc-500 text-[10px] tracking-widest font-medium uppercase mb-2">Public Feed</h2>
      <ul className="space-y-0.5">
        {thoughts.slice(0, 40).map((t, i) => {
          const color = ACTION_COLORS[t.action] || 'text-zinc-500';
          return (
            <li key={i} className="font-mono leading-relaxed">
              <span className="text-zinc-600">T{t.turn}</span>{' '}
              <span className="text-zinc-300">{t.agent_id}</span>{' '}
              <span className={color}>{t.action}</span>
              <span className="text-zinc-600"> {t.outcome}</span>
              {t.public_message && (
                <div className="ml-3 text-zinc-400 italic border-l-2 border-zinc-700 pl-2 mt-0.5">{t.public_message}</div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
