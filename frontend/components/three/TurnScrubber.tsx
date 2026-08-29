'use client';

/**
 * Transport for a replayed run: step, scrub, play.
 *
 * It reports positions in the loaded window, not in the whole run, because a
 * long trace arrives a page at a time and a slider that ranges over turns not
 * yet fetched would let you land on nothing.
 */
export default function TurnScrubber({
  index,
  loaded,
  total,
  turn,
  playing,
  onSeek,
  onTogglePlay,
}: {
  index: number;
  loaded: number;
  total: number;
  turn: number;
  playing: boolean;
  onSeek: (index: number) => void;
  onTogglePlay: () => void;
}) {
  const last = Math.max(0, loaded - 1);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <button
        type="button"
        onClick={onTogglePlay}
        disabled={loaded === 0}
        className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink disabled:opacity-40"
        aria-label={playing ? 'Pause playback' : 'Play the run'}
      >
        {playing ? '⏸ pause' : '▶ play'}
      </button>

      <button
        type="button"
        onClick={() => onSeek(index - 1)}
        disabled={index <= 0}
        className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink disabled:opacity-40"
      >
        ← prev
      </button>
      <button
        type="button"
        onClick={() => onSeek(index + 1)}
        disabled={index >= last}
        className="text-[12px] px-3 py-1 rounded-pill border-[1.5px] border-cozy-card-edge bg-cozy-card text-cozy-ink disabled:opacity-40"
      >
        next →
      </button>

      <input
        type="range"
        min={0}
        max={last}
        value={Math.min(index, last)}
        onChange={(e) => onSeek(Number(e.target.value))}
        disabled={loaded <= 1}
        aria-label="Turn"
        className="flex-1 min-w-[140px] accent-cozy-accent"
      />

      <span className="text-[11px] font-mono text-cozy-ink-soft whitespace-nowrap">
        turn {turn} · {loaded} of {total} loaded
      </span>
    </div>
  );
}
