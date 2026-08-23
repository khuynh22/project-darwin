'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  fetchReleases,
  fetchScores,
  type ModelScore,
  type Rate,
} from '@/lib/releases';

function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

function RateCell({ rate }: { rate: Rate }) {
  if (!rate || rate.n === 0) {
    return <span className="text-cozy-ink-faint">—</span>;
  }
  return (
    <span className="font-mono text-[12px] text-cozy-ink">
      {pct(rate.rate)}
      <span className="text-cozy-ink-faint">
        {' '}
        [{pct(rate.low)}, {pct(rate.high)}] n={rate.n}
      </span>
    </span>
  );
}

export default function LeaderboardPage() {
  const [scores, setScores] = useState<ModelScore[] | null>(null);
  const [source, setSource] = useState<string>('');

  useEffect(() => {
    fetchReleases()
      .then(async (releases) => {
        for (const r of releases) {
          if (!r.has_scores) continue;
          const s = await fetchScores(r.run_id);
          if (s.length) {
            setSource(r.run_id);
            setScores(s);
            return;
          }
        }
        setScores([]);
      })
      .catch(() => setScores([]));
  }, []);

  return (
    <main className="min-h-screen px-5 py-8 md:px-10">
      <header className="max-w-6xl mx-auto mb-5">
        <Link href="/gallery" className="text-[12px] text-cozy-accent hover:underline">
          ← released runs
        </Link>
        <h1 className="font-display font-bold text-[26px] text-cozy-ink mt-1">
          Benchmark leaderboard
        </h1>
        <p className="mt-1 text-[13px] text-cozy-ink-soft max-w-3xl leading-snug">
          Every model faces the same frozen situations, so these scores are comparable in a
          way arena rates are not. Each rate is sampled several times per probe and carries
          a Wilson interval — the stimulus is fixed, the response is not.
        </p>
        {source && (
          <p className="mt-1 text-[11px] font-mono text-cozy-ink-faint">
            source: {source}
          </p>
        )}
      </header>

      <div className="max-w-6xl mx-auto">
        {scores === null && <div className="text-[13px] text-cozy-ink-soft">Loading…</div>}

        {scores?.length === 0 && (
          <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[18px] p-5">
            <div className="font-display font-semibold text-[15px] text-cozy-ink mb-1">
              No scores published yet
            </div>
            <p className="text-[13px] text-cozy-ink-soft leading-snug">
              Publish a <span className="font-mono">scores.json</span> into a release
              directory. Generate one with{' '}
              <span className="font-mono">darwin probe run</span> then{' '}
              <span className="font-mono">darwin probe score</span>.
            </p>
          </div>
        )}

        {scores && scores.length > 0 && (
          <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[20px] p-4 shadow-cozy overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.1em] text-cozy-ink-soft">
                  <th className="py-2 pr-4">model</th>
                  <th className="py-2 pr-4">propensity</th>
                  <th className="py-2 pr-4">pressure threshold</th>
                  <th className="py-2 pr-4">susceptibility</th>
                  <th className="py-2 pr-4">sophistication</th>
                  <th className="py-2 pr-4">excluded</th>
                  <th className="py-2">divergence</th>
                </tr>
              </thead>
              <tbody>
                {scores.map((s) => (
                  <tr
                    key={s.model}
                    className="border-t border-dashed border-cozy-card-edge align-top"
                  >
                    <td className="py-2 pr-4 font-mono text-[12px] text-cozy-ink">
                      {s.model}
                    </td>
                    <td className="py-2 pr-4">
                      <RateCell rate={s.propensity_overall} />
                      {Object.keys(s.propensity_by_tier ?? {}).length > 0 && (
                        <div className="mt-1 flex gap-2 flex-wrap">
                          {Object.entries(s.propensity_by_tier).map(([tier, r]) => (
                            <span
                              key={tier}
                              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cozy-bg2 text-cozy-ink-soft"
                            >
                              L{tier} {pct(r.rate)} (n={r.n})
                            </span>
                          ))}
                        </div>
                      )}
                      {s.untiered > 0 && (
                        <div className="mt-1 text-[10px] text-cozy-ink-faint">
                          {s.untiered} runs untiered — absent from the curve
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-4 font-mono text-[12px] text-cozy-ink">
                      {s.pressure_threshold ? (
                        `L${s.pressure_threshold}`
                      ) : (
                        <span className="text-cozy-ink-faint">none established</span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <RateCell rate={s.susceptibility} />
                    </td>
                    <td className="py-2 pr-4 font-mono text-[12px] text-cozy-ink">
                      {s.sophistication_mean != null ? (
                        s.sophistication_mean.toFixed(2)
                      ) : (
                        <span className="text-cozy-ink-faint">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 font-mono text-[12px] text-cozy-ink-soft">
                      {s.excluded}
                    </td>
                    <td className="py-2 font-mono text-[12px] text-cozy-ink-soft">
                      {pct(s.divergence_mean)}
                      <span className="text-cozy-ink-faint">
                        {' '}
                        max {pct(s.divergence_max)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="mt-3 pt-3 border-t border-dashed border-cozy-card-edge text-[11px] leading-snug text-cozy-ink-soft">
              <strong>Excluded</strong> counts probe runs where replayed opponents diverged
              past the threshold; those runs are dropped rather than repaired.{' '}
              <strong>Divergence</strong> is reported over every run, excluded ones
              included — a suite that reports divergence only for the probes it kept is
              describing its own filter.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
