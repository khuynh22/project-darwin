'use client';

import Link from 'next/link';
import { use, useCallback, useEffect, useMemo, useState } from 'react';
import TurnCard from '@/components/TurnCard';
import {
  fetchRelease,
  fetchTurns,
  fetchVerdicts,
  indexVerdicts,
  verdictKey,
  type ReleaseDetail,
  type ReleaseTurn,
  type Verdict,
} from '@/lib/releases';

const PAGE = 40;

export default function ReplayPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = use(params);
  const decoded = decodeURIComponent(runId);

  const [detail, setDetail] = useState<ReleaseDetail | null>(null);
  const [turns, setTurns] = useState<ReleaseTurn[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [agent, setAgent] = useState('');
  const [deceptiveOnly, setDeceptiveOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRelease(decoded).then(setDetail).catch((e) => setError(String(e)));
    fetchVerdicts(decoded).then(setVerdicts).catch(() => setVerdicts([]));
  }, [decoded]);

  const load = useCallback(
    (next: number) => {
      fetchTurns(decoded, next, PAGE)
        .then((page) => {
          setTurns(page.turns);
          setTotal(page.total);
          setOffset(page.offset);
        })
        .catch((e) => setError(String(e)));
    },
    [decoded],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  const index = useMemo(() => indexVerdicts(verdicts), [verdicts]);

  const visible = useMemo(() => {
    let rows = turns;
    if (agent) rows = rows.filter((t) => t.agent_id === agent);
    if (deceptiveOnly) {
      rows = rows.filter(
        (t) => index.get(verdictKey(t.turn, t.agent_id))?.is_deceptive === true,
      );
    }
    return rows;
  }, [turns, agent, deceptiveOnly, index]);

  const nDeceptive = useMemo(
    () => verdicts.filter((v) => v.is_deceptive).length,
    [verdicts],
  );

  return (
    <main className="min-h-screen px-5 py-8 md:px-10">
      <header className="max-w-5xl mx-auto mb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <Link href="/gallery" className="text-[12px] text-cozy-accent hover:underline">
            ← all releases
          </Link>
          <Link
            href={`/gallery/${encodeURIComponent(decoded)}/3d`}
            className="text-[12px] text-cozy-accent hover:underline"
          >
            3-D world →
          </Link>
        </div>
        <h1 className="font-display font-bold text-[22px] text-cozy-ink mt-1">
          {decoded}
        </h1>
        {detail && (
          <div className="flex gap-3 flex-wrap text-[12px] font-mono text-cozy-ink-soft mt-1">
            <span>{detail.horizon} turns</span>
            <span>{detail.n_agents} agents</span>
            <span>{detail.condition}</span>
            <span>{detail.state_fidelity} state</span>
            {verdicts.length > 0 && (
              <span>
                {nDeceptive}/{verdicts.length} judged deceptive
              </span>
            )}
          </div>
        )}
        {detail?.about && (
          <details className="mt-3 bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[16px] px-4 py-3">
            <summary className="cursor-pointer font-display font-semibold text-[13px] text-cozy-ink">
              About this run — read the caveats
            </summary>
            <pre className="mt-2 text-[12px] leading-snug text-cozy-ink-soft whitespace-pre-wrap font-sans">
              {detail.about}
            </pre>
          </details>
        )}
      </header>

      <div className="max-w-5xl mx-auto min-w-0">
        {error && (
          <div className="mb-3 text-[13px] text-cozy-ink-soft">
            Could not load: <span className="font-mono">{error}</span>
          </div>
        )}

        <div className="flex items-center gap-2 flex-wrap mb-3">
          <select
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            className="text-[12px] font-mono px-2 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink"
          >
            <option value="">all agents</option>
            {(detail?.agents ?? []).map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.agent_id}
              </option>
            ))}
          </select>

          <label className="flex items-center gap-1.5 text-[12px] text-cozy-ink-soft">
            <input
              type="checkbox"
              checked={deceptiveOnly}
              onChange={(e) => setDeceptiveOnly(e.target.checked)}
              disabled={verdicts.length === 0}
            />
            deceptive only
          </label>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => load(Math.max(0, offset - PAGE))}
              disabled={offset === 0}
              className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink disabled:opacity-40"
            >
              ← prev
            </button>
            <span className="text-[11px] font-mono text-cozy-ink-soft">
              {total ? offset + 1 : 0}–{Math.min(offset + PAGE, total)} of {total}
            </span>
            <button
              onClick={() => load(offset + PAGE)}
              disabled={offset + PAGE >= total}
              className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink disabled:opacity-40"
            >
              next →
            </button>
          </div>
        </div>

        {visible.length === 0 && turns.length > 0 && (
          <div className="text-[13px] text-cozy-ink-soft">
            No turns on this page match the filter. Filters apply to the loaded page, not
            the whole run — try paging on.
          </div>
        )}

        <div className="grid gap-2 min-w-0">
          {visible.map((t) => (
            <TurnCard
              key={`${t.turn}:${t.agent_id}`}
              turn={t}
              verdict={index.get(verdictKey(t.turn, t.agent_id))}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
