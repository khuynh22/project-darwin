'use client';

import type { Verdict } from '@/lib/releases';

export const TYPE_LABEL: Record<string, string> = {
  false_state_claim: 'false state claim',
  false_promise: 'false promise',
  strategic_omission: 'strategic omission',
  misdirection: 'misdirection',
  identity_bluff: 'identity bluff',
};

export const SOPHISTICATION_LABEL: Record<number, string> = {
  1: 'omission',
  2: 'misdirection',
  3: 'false statement',
  4: 'fabricated evidence',
  5: 'sustained campaign',
};

/**
 * One channel of the triple.
 *
 * Shared rather than copied: the turn list and the 3-D panel are the two
 * places a reader compares what an agent thought, said and did, and two
 * presentations of that comparison would be two instruments.
 */
export function Channel({
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

export function VerdictRow({ verdict }: { verdict: Verdict }) {
  return (
    <div className="mt-2 pt-2 border-t border-dashed border-cozy-card-edge">
      <div className="flex items-center gap-2 flex-wrap text-[11px] text-cozy-ink-soft">
        <span className="font-bold uppercase tracking-[0.1em] text-[9px]">judge</span>
        <span className="text-cozy-ink font-semibold">
          {verdict.is_deceptive
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
  );
}
