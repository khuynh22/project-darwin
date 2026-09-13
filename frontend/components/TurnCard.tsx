'use client';

import { Channel, VerdictRow } from '@/components/Triple';
import type { ReleaseTurn, Verdict } from '@/lib/releases';

export default function TurnCard({
  turn,
  verdict,
}: {
  turn: ReleaseTurn;
  verdict?: Verdict;
}) {
  const deceptive = verdict?.is_deceptive === true;
  const args = Object.keys(turn.arguments ?? {}).length
    ? JSON.stringify(turn.arguments)
    : '';

  return (
    <div
      className="bg-cozy-card border-[1.5px] rounded-[18px] p-3 shadow-cozy min-w-0 overflow-hidden"
      style={{ borderColor: deceptive ? '#E68A8A' : '#F0E2C8' }}
    >
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <span className="font-mono text-[11px] font-bold text-cozy-ink-soft">
          t{turn.turn}
        </span>
        <span className="font-display font-semibold text-[13px] text-cozy-ink">
          {turn.agent_id}
        </span>
        <span className="font-mono text-[11px] px-2 py-0.5 rounded-pill bg-cozy-bg2 text-cozy-ink break-all">
          {turn.action}
          {args && <span className="text-cozy-ink-faint"> {args}</span>}
        </span>
        {!turn.instrument.tool_call_ok && (
          <span
            className="text-[10px] px-2 py-0.5 rounded-pill font-bold"
            style={{ background: 'rgba(230,181,112,0.25)', color: '#8B7560' }}
            title="The provider returned no usable tool call. Not a decision, and excluded from judging."
          >
            tool-call fallback
          </span>
        )}
        {deceptive && (
          <span
            className="ml-auto text-[10px] px-2 py-0.5 rounded-pill font-bold"
            style={{ background: 'rgba(230,138,138,0.22)', color: '#A85A5A' }}
          >
            deceptive
          </span>
        )}
      </div>

      <div className="grid gap-1.5 md:grid-cols-3 min-w-0">
        <Channel label="private reasoning" body={turn.monologue} tone="private" />
        <Channel label="public message" body={turn.public_message} tone="public" />
        <Channel label="applied action" body={turn.outcome} tone="action" />
      </div>

      {verdict && <VerdictRow verdict={verdict} />}
    </div>
  );
}
