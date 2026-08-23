'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { fetchReleases, type ReleaseSummary } from '@/lib/releases';

function FidelityBadge({ fidelity }: { fidelity: string }) {
  const partial = fidelity === 'partial';
  return (
    <span
      className="text-[10px] px-2 py-0.5 rounded-pill font-bold"
      style={{
        background: partial ? 'rgba(230,181,112,0.25)' : 'rgba(111,191,142,0.2)',
        color: partial ? '#8B6A3A' : '#3F7A57',
      }}
      title={
        partial
          ? 'This trace carries the triple but no per-turn world state, so probes mined from it have no pressure tier.'
          : 'Per-turn world state is recorded, so the frozen moment can be restored exactly.'
      }
    >
      {partial ? 'partial state' : 'full state'}
    </span>
  );
}

export default function GalleryPage() {
  const [releases, setReleases] = useState<ReleaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReleases()
      .then(setReleases)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="min-h-screen px-5 py-8 md:px-10">
      <header className="max-w-5xl mx-auto mb-6">
        <div className="flex items-baseline gap-3 flex-wrap">
          <h1 className="font-display font-bold text-[26px] text-cozy-ink">
            Released runs
          </h1>
          <Link
            href="/leaderboard"
            className="text-[12px] font-semibold text-cozy-accent hover:underline"
          >
            benchmark leaderboard →
          </Link>
        </div>
        <p className="mt-1 text-[13px] text-cozy-ink-soft max-w-2xl leading-snug">
          Every agent-turn is recorded as a triple — the stated private reasoning, the
          public broadcast, and the action the engine actually applied. A turn is labelled
          deceptive only when those channels contradict.
        </p>
      </header>

      <div className="max-w-5xl mx-auto">
        {error && (
          <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[18px] p-4 text-[13px] text-cozy-ink-soft">
            Could not reach the Oracle: <span className="font-mono">{error}</span>
          </div>
        )}

        {!error && releases === null && (
          <div className="text-[13px] text-cozy-ink-soft">Loading…</div>
        )}

        {releases?.length === 0 && (
          <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[18px] p-5">
            <div className="font-display font-semibold text-[15px] text-cozy-ink mb-1">
              Nothing published yet
            </div>
            <p className="text-[13px] text-cozy-ink-soft leading-snug">
              Populate <span className="font-mono">releases/&lt;run_id&gt;/</span> with a{' '}
              <span className="font-mono">trace.jsonl</span> — see{' '}
              <span className="font-mono">releases/README.md</span>.
            </p>
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          {(releases ?? []).map((r) => (
            <Link
              key={r.run_id}
              href={`/gallery/${encodeURIComponent(r.run_id)}`}
              className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[20px] p-4 shadow-cozy hover:shadow-cozy-md transition-shadow"
            >
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="font-display font-semibold text-[15px] text-cozy-ink">
                  {r.run_id}
                </span>
                <FidelityBadge fidelity={r.state_fidelity} />
              </div>
              <div className="flex gap-3 flex-wrap text-[12px] text-cozy-ink-soft font-mono mb-2">
                <span>{r.horizon} turns</span>
                <span>{r.n_agents} agents</span>
                <span>{r.n_turns.toLocaleString()} rows</span>
                <span>{r.condition}</span>
                {r.has_verdicts && <span className="text-cozy-accent">judged</span>}
              </div>
              <div className="flex gap-1 flex-wrap">
                {r.models.slice(0, 6).map((m) => (
                  <span
                    key={m}
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cozy-bg2 text-cozy-ink-soft"
                  >
                    {m}
                  </span>
                ))}
                {r.models.length > 6 && (
                  <span className="text-[10px] text-cozy-ink-faint">
                    +{r.models.length - 6}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
