'use client';

import type { WorldSnapshot } from '@/lib/ws';

export default function ThoughtLog({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const thoughts = snapshot?.recent_thoughts ?? [];
  return (
    <section className="h-56 bg-arena-panel border-t border-black/40 overflow-y-auto p-3 text-xs">
      <h2 className="text-arena-accent tracking-widest mb-2">INTERNAL MONOLOGUE</h2>
      <ul className="space-y-1">
        {thoughts.slice(0, 30).map((t, i) => (
          <li key={i} className="font-mono">
            <span className="text-arena-accent">[T{t.turn} {t.agent_id}]</span>{' '}
            <span className="text-white/80">{t.monologue}</span>
            <span className="text-white/40">  → {t.action}({JSON.stringify(t.arguments)}) :: {t.outcome}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
