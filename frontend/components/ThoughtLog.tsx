'use client';

import { Brain } from 'lucide-react';
import type { WorldSnapshot } from '@/lib/ws';

export default function ThoughtLog({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const thoughts = snapshot?.recent_thoughts ?? [];
  return (
    <section className="flex-1 bg-zinc-950/60 overflow-y-auto p-3 text-xs">
      <h2 className="flex items-center gap-1.5 text-zinc-500 text-[10px] tracking-widest font-medium uppercase mb-2">
        <Brain size={10} /> Private Thoughts
      </h2>
      <ul className="space-y-0.5">
        {thoughts.slice(0, 40).map((t, i) => (
          <li key={i} className="font-mono leading-relaxed">
            <span className="text-zinc-700">T{t.turn} {t.agent_id}</span>{' '}
            <span className="text-zinc-500">{t.monologue || '(no reasoning)'}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
