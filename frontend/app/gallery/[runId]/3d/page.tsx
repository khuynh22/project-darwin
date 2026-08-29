'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { use, useEffect, useMemo, useState } from 'react';
import { buildFramesFromTurns, type WorldFrame } from '@/lib/frame';
import {
  fetchRelease,
  fetchTurns,
  fetchVerdicts,
  type ReleaseDetail,
} from '@/lib/releases';
import TriplePanel from '@/components/three/TriplePanel';
import { hasWebGL } from '@/lib/world3d';

const PAGE = 200;

// The scene pulls in three.js, which has no business in the server bundle and
// no business loading at all for a viewer that cannot render it.
const WorldScene = dynamic(() => import('@/components/three/WorldScene'), {
  ssr: false,
  loading: () => <div className="text-[13px] text-cozy-ink-soft">Loading world…</div>,
});

export default function World3DPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = use(params);
  const decoded = decodeURIComponent(runId);

  const [detail, setDetail] = useState<ReleaseDetail | null>(null);
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [frames, setFrames] = useState<WorldFrame[]>([]);
  const [cursor] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setWebgl(hasWebGL());
    fetchRelease(decoded).then(setDetail).catch(() => setDetail(null));
    Promise.all([fetchTurns(decoded, 0, PAGE), fetchVerdicts(decoded)])
      .then(([page, verdicts]) => setFrames(buildFramesFromTurns(page.turns, verdicts)))
      .catch(() => setFrames([]));
  }, [decoded]);

  const frame = frames[cursor] ?? null;

  // Something is always selected once a turn is loaded: an empty panel beside
  // a full world reads as broken rather than as "nothing chosen yet".
  const selected = useMemo(() => {
    if (!frame) return null;
    return (
      frame.agents.find((a) => a.agentId === selectedId) ?? frame.agents[0] ?? null
    );
  }, [frame, selectedId]);

  return (
    <main className="min-h-screen px-5 py-6 md:px-10">
      <header className="max-w-[1400px] mx-auto mb-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            href={`/gallery/${encodeURIComponent(decoded)}`}
            className="text-[12px] text-cozy-accent hover:underline"
          >
            ← turn-by-turn view
          </Link>
          <span className="text-[11px] text-cozy-ink-faint">
            drag to orbit · scroll to zoom · click an agent
          </span>
        </div>
        <h1 className="font-display font-bold text-[22px] text-cozy-ink mt-1">
          {decoded}
        </h1>
        {detail && (
          <div className="flex gap-3 flex-wrap text-[12px] font-mono text-cozy-ink-soft mt-1">
            <span>{detail.horizon} turns</span>
            <span>{detail.n_agents} agents</span>
            <span>{detail.state_fidelity} state</span>
          </div>
        )}
      </header>

      <div className="max-w-[1400px] mx-auto">
        {webgl === false && (
          <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[18px] p-5">
            <div className="font-display font-semibold text-[15px] text-cozy-ink mb-1">
              This browser cannot render the 3-D view
            </div>
            <p className="text-[13px] text-cozy-ink-soft leading-snug">
              WebGL is unavailable or disabled. The{' '}
              <Link
                href={`/gallery/${encodeURIComponent(decoded)}`}
                className="text-cozy-accent hover:underline"
              >
                turn-by-turn view
              </Link>{' '}
              shows the same run, and it is the one that shows the judge&apos;s verdict
              beside each turn.
            </p>
          </div>
        )}

        {webgl && (
          <div className="grid gap-3 lg:grid-cols-[1fr_380px] items-start">
            <div
              className="rounded-[20px] overflow-hidden border-[1.5px] border-cozy-card-edge shadow-cozy bg-cozy-bg1"
              style={{ aspectRatio: '16 / 10', maxHeight: '72vh', minHeight: 300 }}
            >
              <WorldScene
                frame={frame}
                selectedId={selected?.agentId ?? null}
                onSelect={setSelectedId}
              />
            </div>
            <div className="min-w-0 lg:max-h-[72vh] lg:overflow-y-auto">
              <TriplePanel agent={selected} turn={frame?.turn ?? 0} />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
