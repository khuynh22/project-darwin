'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { use, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import TriplePanel from '@/components/three/TriplePanel';
import TurnScrubber from '@/components/three/TurnScrubber';
import type { ViewMode } from '@/components/three/WorldScene';
import { buildFramesFromTurns } from '@/lib/frame';
import {
  fetchRelease,
  fetchTurns,
  fetchVerdicts,
  type ReleaseDetail,
  type ReleaseTurn,
  type Verdict,
} from '@/lib/releases';
import { hasWebGL } from '@/lib/world3d';

const PAGE = 200;

// Live auto-play waits 3700ms so a critter's walk lands before the next turn.
// Nothing walks here -- pawns are positioned, not animated -- so playback runs
// at reading speed instead.
const PLAYBACK_DELAY_MS = 700;

// Fetch the next page while there is still this much loaded run ahead of the
// cursor, so scrubbing forward does not stall on a request.
const PREFETCH_MARGIN = 20;

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
  const [turns, setTurns] = useState<ReleaseTurn[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>('walk');
  const [locked, setLocked] = useState(false);
  const [hud, setHud] = useState(true);

  // Guards the pager against a second request for a page already in flight;
  // the cursor can cross the margin several times while one is pending.
  const loading = useRef(false);

  useEffect(() => {
    setWebgl(hasWebGL());
    fetchRelease(decoded).then(setDetail).catch(() => setDetail(null));
    fetchVerdicts(decoded).then(setVerdicts).catch(() => setVerdicts([]));
  }, [decoded]);

  const loadPage = useCallback(
    (offset: number) => {
      if (loading.current) return;
      loading.current = true;
      fetchTurns(decoded, offset, PAGE)
        .then((page) => {
          setTotal(page.total);
          setTurns((prev) =>
            page.offset === 0 ? page.turns : [...prev, ...page.turns],
          );
        })
        .catch(() => undefined)
        .finally(() => {
          loading.current = false;
        });
    },
    [decoded],
  );

  useEffect(() => {
    setTurns([]);
    setCursor(0);
    loadPage(0);
  }, [loadPage]);

  const frames = useMemo(
    () => buildFramesFromTurns(turns, verdicts),
    [turns, verdicts],
  );

  useEffect(() => {
    if (turns.length >= total) return;
    if (cursor < frames.length - PREFETCH_MARGIN) return;
    loadPage(turns.length);
  }, [cursor, frames.length, turns.length, total, loadPage]);

  useEffect(() => {
    if (!playing || frames.length === 0) return;
    const id = setInterval(() => {
      setCursor((c) => {
        if (c + 1 >= frames.length) {
          setPlaying(false);
          return c;
        }
        return c + 1;
      });
    }, PLAYBACK_DELAY_MS);
    return () => clearInterval(id);
  }, [playing, frames.length]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== 'KeyH' || e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;
      setHud((v) => !v);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const seek = useCallback(
    (next: number) => setCursor(Math.max(0, Math.min(next, frames.length - 1))),
    [frames.length],
  );

  const frame = frames[Math.min(cursor, Math.max(0, frames.length - 1))] ?? null;

  const selected = useMemo(() => {
    if (!frame) return null;
    const named = frame.agents.find((a) => a.agentId === selectedId) ?? null;
    // On foot the panel shows whoever you are standing in front of, and nobody
    // when you are standing alone — falling back to the first agent would put
    // words in the mouth of someone across the plaza. From above there is
    // always a selection, because an empty panel beside a full world reads as
    // broken rather than as "nothing chosen yet".
    if (mode === 'walk') return named;
    return named ?? frame.agents[0] ?? null;
  }, [frame, selectedId, mode]);

  return (
    <main className="fixed inset-0 overflow-hidden bg-cozy-bg1">
      {webgl === false && (
        <div className="h-full grid place-items-center px-5">
          <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[18px] p-5 max-w-md shadow-cozy">
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
        </div>
      )}

      {webgl && (
        <>
          {/* The world takes the whole viewport. Everything else floats on it. */}
          <div className="absolute inset-0">
            <WorldScene
              frame={frame}
              mode={mode}
              selectedId={selected?.agentId ?? null}
              onSelect={setSelectedId}
              onLockChange={setLocked}
            />
          </div>

          {mode === 'walk' && !locked && (
            <div className="absolute inset-0 grid place-items-center pointer-events-none">
              <div className="px-4 py-2 rounded-pill bg-cozy-card/90 border-[1.5px] border-cozy-card-edge text-[12px] text-cozy-ink shadow-cozy">
                Click to look around
              </div>
            </div>
          )}

          {/* Nothing in the overlay layer eats a click unless it is a control:
              the canvas underneath needs the click that grabs the pointer. */}
          <div className="absolute inset-0 pointer-events-none flex flex-col gap-3 p-3 md:p-4">
            {hud && (
              <div className="flex items-start gap-2 flex-wrap pointer-events-auto">
                <div className="flex items-center gap-2 flex-wrap rounded-[16px] bg-cozy-card/92 border-[1.5px] border-cozy-card-edge shadow-cozy px-3 py-2 backdrop-blur-sm">
                  <Link
                    href={`/gallery/${encodeURIComponent(decoded)}`}
                    className="text-[12px] text-cozy-accent hover:underline"
                  >
                    ← turn-by-turn
                  </Link>
                  <span className="font-display font-bold text-[13px] text-cozy-ink">
                    {decoded}
                  </span>
                  {detail && (
                    <span className="text-[11px] font-mono text-cozy-ink-soft">
                      {detail.horizon} turns · {detail.n_agents} agents ·{' '}
                      {detail.state_fidelity} state
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setMode((m) => (m === 'walk' ? 'overview' : 'walk'))}
                    className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink"
                  >
                    {mode === 'walk' ? '↑ overview' : '↓ walk the town'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setHud(false)}
                    className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink"
                    title="Hide the overlay (H)"
                  >
                    hide
                  </button>
                </div>
                <span className="text-[11px] text-cozy-ink-faint bg-cozy-card/80 rounded-pill px-2.5 py-1.5">
                  {mode === 'walk'
                    ? 'click to look · WASD to walk · shift to run · esc to let go'
                    : 'drag to orbit · scroll to zoom · click an agent'}
                </span>
              </div>
            )}

            {!hud && (
              <button
                type="button"
                onClick={() => setHud(true)}
                className="self-start pointer-events-auto text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card/90 text-cozy-ink"
              >
                show overlay
              </button>
            )}

            {hud && (
              <div className="flex-1 min-h-0 flex justify-end">
                <div className="w-[380px] max-w-[calc(100vw-1.5rem)] overflow-y-auto pointer-events-auto">
                  <TriplePanel
                    agent={selected}
                    turn={frame?.turn ?? 0}
                    emptyHint={
                      mode === 'walk'
                        ? 'Walk up to an agent to read what it thought, what it said, and what it did on this turn.'
                        : undefined
                    }
                  />
                </div>
              </div>
            )}

            {hud && (
              <div className="pointer-events-auto rounded-[16px] bg-cozy-card/92 border-[1.5px] border-cozy-card-edge shadow-cozy px-3 py-2 backdrop-blur-sm">
                <TurnScrubber
                  index={cursor}
                  loaded={frames.length}
                  total={detail?.horizon ?? frames.length}
                  turn={frame?.turn ?? 0}
                  playing={playing}
                  onSeek={seek}
                  onTogglePlay={() => setPlaying((p) => !p)}
                />
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}
