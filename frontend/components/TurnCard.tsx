'use client';

import type { ReleaseTurn, Verdict } from '@/lib/releases';

const TYPE_LABEL: Record<string, string> = {
  false_state_claim: 'false state claim',
  false_promise: 'false promise',
  strategic_omission: 'strategic omission',
  misdirection: 'misdirection',
  identity_bluff: 'identity bluff',
};

const SOPHISTICATION_LABEL: Record<number, string> = {
  1: 'omission',
  2: 'misdirection',
  3: 'false statement',
  4: 'fabricated evidence',
  5: 'sustained campaign',
};

function Channel({
  label,
  body,
  tone,
}: {
  label: string;
  body: string;
  tone: 'private' | 'public' | 'action';
}) {
  const bg =
    tone === 'private'
      ? 'rgba(181,148,216,0.14)'
      : tone === 'public'
        ? 'rgba(125,167,225,0.14)'
        : 'rgba(111,191,142,0.14)';
  return (
    <div className="rounded-[12px] px-3 py-2 min-w-0" style={{ background: bg }}>
      <div className="text-[9px] uppercase tracking-[0.12em] font-bold text-cozy-ink-soft mb-1">
        {label}
      </div>
      <div className="text-[12px] leading-snug text-cozy-ink whitespace-pre-wrap break-words">
        {body || <span className="text-cozy-ink-faint">—</span>}
      </div>
    </div>
  );
}

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

      {verdict && (
        <div className="mt-2 pt-2 border-t border-dashed border-cozy-card-edge">
          <div className="flex items-center gap-2 flex-wrap text-[11px] text-cozy-ink-soft">
            <span className="font-bold uppercase tracking-[0.1em] text-[9px]">
              judge
            </span>
            <span className="text-cozy-ink font-semibold">
              {deceptive
                ? (TYPE_LABEL[verdict.deception_type] ?? verdict.deception_type)
                : 'no contradiction'}
            </span>
            {verdict.target_id && <span>→ {verdict.target_id}</span>}
            <span className="font-mono">conf {verdict.confidence.toFixed(2)}</span>
            {verdict.sophistication != null && (
              <span className="font-mono">
                soph {verdict.sophistication}
                <span className="text-cozy-ink-faint">
                  {' '}
                  {SOPHISTICATION_LABEL[verdict.sophistication]}
                </span>
              </span>
            )}
          </div>
          {verdict.rationale && (
            <div className="mt-1 text-[11px] leading-snug text-cozy-ink-soft italic">
              {verdict.rationale}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
