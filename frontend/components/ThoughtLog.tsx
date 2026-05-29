'use client';

import { useEffect, useMemo, useRef } from 'react';
import type { WorldSnapshot } from '@/lib/ws';
import { COLOR_HEX } from '@/lib/town';

interface ThoughtLogProps {
  snapshot: WorldSnapshot | null;
}

export default function ThoughtLog({ snapshot }: ThoughtLogProps) {
  const agents = snapshot?.agents ?? [];

  const rows = useMemo(() => {
    return [...(snapshot?.recent_thoughts ?? [])].slice(0, 40).reverse();
  }, [snapshot?.recent_thoughts]);

  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [rows.length]);

  return (
    <div
      className="flex flex-col bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[20px] p-3 shadow-cozy"
      style={{ minHeight: 160, maxHeight: 200 }}
    >
      <div className="flex items-center gap-2 pb-2 border-b border-dashed border-cozy-card-edge mb-2 px-0.5">
        <div
          className="w-6 h-6 grid place-items-center rounded-lg text-[13px]"
          style={{ background: 'rgba(181,148,216,0.25)' }}
        >
          💭
        </div>
        <div className="font-display font-semibold text-[14px] text-cozy-ink">Inner Thoughts</div>
        <div className="ml-auto text-[10px] uppercase tracking-[0.1em] font-bold text-cozy-ink-soft">
          private monologues
        </div>
      </div>

      <div ref={bodyRef} className="flex-1 overflow-y-auto pr-1">
        {rows.length === 0 && (
          <div className="text-cozy-ink-faint italic px-1 py-2 text-[13px]">…minds at ease…</div>
        )}
        {rows.map((row, i) => {
          const agent = agents.find((a) => a.agent_id === row.agent_id);
          const color = agent ? COLOR_HEX[agent.sprite] || '#FFCBA0' : '#C4B59A';
          const name = agent?.display_name || row.agent_id;
          return (
            <div
              key={`${row.turn}-${row.agent_id}-${i}`}
              className="flex gap-2 py-[6px] px-1 text-[13px] leading-snug animate-log-in"
            >
              <div
                className="w-4 h-4 rounded-full flex-shrink-0 mt-[2px]"
                style={{
                  background: color,
                  boxShadow: 'inset 0 -2px 0 rgba(0,0,0,0.1)',
                }}
              />
              <div className="flex-1">
                <span className="font-display font-semibold text-cozy-ink not-italic">
                  {name}
                </span>{' '}
                <span className="text-cozy-ink-soft italic">
                  — {row.monologue || '(silent)'}
                </span>
              </div>
              <div className="font-mono text-[10px] text-cozy-ink-faint flex-shrink-0">
                T{String(row.turn).padStart(2, '0')}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
