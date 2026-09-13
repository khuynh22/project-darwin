'use client';

import { Channel, VerdictRow } from '@/components/Triple';
import type { FrameAgent } from '@/lib/frame';

/**
 * The selected agent-turn's triple, docked beside the world.
 *
 * Channels stack rather than sitting in three columns: the S1 spike measured
 * both, and three columns inside a 380px dock leaves ~110px each. The dock
 * itself was chosen over an in-canvas overlay because the overlay hid two of
 * the six venues at 1280x800.
 *
 * With the 2-D view gone this panel is the only place the triple is legible,
 * which makes it the acceptance criterion of the whole 3-D view rather than a
 * nicety (spec 2026-08-24 §6, ADR 2026-08-26-3d-primary-renderer).
 */
export default function TriplePanel({
  agent,
  turn,
  emptyHint = 'Select an agent in the world to read what it thought, what it said, and what it did on this turn.',
}: {
  agent: FrameAgent | null;
  turn: number;
  emptyHint?: string;
}) {
  if (!agent) {
    return (
      <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[18px] p-4 shadow-cozy">
        <div className="text-[13px] text-cozy-ink-soft leading-snug">{emptyHint}</div>
      </div>
    );
  }

  const deceptive = agent.verdict?.is_deceptive === true;

  return (
    <div
      className="bg-cozy-card border-[1.5px] rounded-[18px] p-3 shadow-cozy min-w-0 overflow-hidden"
      style={{ borderColor: deceptive ? '#E68A8A' : '#F0E2C8' }}
    >
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <span className="font-mono text-[11px] font-bold text-cozy-ink-soft">
          t{turn}
        </span>
        <span
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{ background: agent.color }}
          aria-hidden
        />
        <span className="font-display font-semibold text-[13px] text-cozy-ink">
          {agent.agentId}
        </span>
        <span className="font-mono text-[11px] px-2 py-0.5 rounded-pill bg-cozy-bg2 text-cozy-ink break-all">
          {agent.action || '—'}
        </span>
        {deceptive && (
          <span
            className="ml-auto text-[10px] px-2 py-0.5 rounded-pill font-bold"
            style={{ background: 'rgba(230,138,138,0.22)', color: '#A85A5A' }}
          >
            deceptive
          </span>
        )}
      </div>

      <div className="grid gap-1.5 min-w-0">
        <Channel label="private reasoning" body={agent.monologue} tone="private" />
        <Channel label="public message" body={agent.publicMessage} tone="public" />
        <Channel label="applied action" body={agent.outcome} tone="action" />
      </div>

      {agent.verdict ? (
        <VerdictRow verdict={agent.verdict} />
      ) : (
        <div className="mt-2 pt-2 border-t border-dashed border-cozy-card-edge text-[11px] text-cozy-ink-faint">
          No verdict — the judge runs offline, after the run.
        </div>
      )}
    </div>
  );
}
