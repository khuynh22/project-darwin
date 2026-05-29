'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';

export type CritterState = 'idle' | 'thinking' | 'acting';

export type Bubble =
  | { kind: 'dots' }
  | { kind: 'intent'; emoji: string; text: string; tint?: string };

export type DeltaFloat = { amount: number; key: number } | null;

interface CritterProps {
  agentId: string;
  color: string;
  name: string;
  balance: number;
  showBalance?: boolean;
  alive?: boolean;
  state?: CritterState;
  bubble?: Bubble | null;
  target: { x: number; y: number };
  facing?: 1 | -1;
  delta?: DeltaFloat;
  onArrive?: (agentId: string) => void;
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// Subtle perpendicular sway so the walk waddles instead of sliding on a rail.
function walkSway(progress: number, dist: number): number {
  const taper = Math.sin(progress * Math.PI);
  const swayAmp = Math.min(6, dist * 0.012);
  return Math.sin(progress * Math.PI * 3) * swayAmp * taper;
}

export default function Critter({
  agentId,
  color,
  name,
  balance,
  showBalance = true,
  alive = true,
  state = 'idle',
  bubble = null,
  target,
  facing = 1,
  delta = null,
  onArrive,
}: CritterProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const posRef = useRef({ x: target.x, y: target.y });
  const animRef = useRef<number | null>(null);
  const arriveRef = useRef(onArrive);
  arriveRef.current = onArrive;

  const [walking, setWalking] = useState(false);
  const [dust, setDust] = useState<Array<{ id: number; dx: number }>>([]);
  const dustKeyRef = useRef(0);

  useLayoutEffect(() => {
    if (wrapRef.current) {
      wrapRef.current.style.transform = `translate(${posRef.current.x}px, ${posRef.current.y}px)`;
    }
  }, []);

  useEffect(() => {
    const start = { ...posRef.current };
    const end = { x: target.x, y: target.y };
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dist = Math.hypot(dx, dy);

    if (dist < 4) {
      if (wrapRef.current) {
        wrapRef.current.style.transform = `translate(${end.x}px, ${end.y}px)`;
      }
      posRef.current = end;
      arriveRef.current?.(agentId);
      return;
    }

    // Distance-scaled travel time — feels like walking, not warping.
    const duration = Math.max(900, Math.min(2800, 700 + dist * 3.4));
    setWalking(true);
    const t0 = performance.now();

    const emitDust = () => {
      const id = ++dustKeyRef.current;
      const ddx = (Math.random() - 0.5) * 18;
      setDust((d) => [...d, { id, dx: ddx }]);
      setTimeout(() => setDust((d) => d.filter((x) => x.id !== id)), 800);
    };
    const dustTimer = setInterval(emitDust, 210);
    const initialDust = setTimeout(emitDust, 60);

    function frame(now: number) {
      const t = Math.min(1, (now - t0) / duration);
      const e = easeInOutCubic(t);
      const sway = walkSway(t, dist);
      const len = dist || 1;
      const perpX = -dy / len;
      const perpY = dx / len;
      const x = start.x + dx * e + perpX * sway;
      const y = start.y + dy * e + perpY * sway;
      posRef.current = { x, y };
      if (wrapRef.current) {
        wrapRef.current.style.transform = `translate(${x}px, ${y}px)`;
      }
      if (t < 1) {
        animRef.current = requestAnimationFrame(frame);
      } else {
        clearInterval(dustTimer);
        const t1 = performance.now();
        const settleDur = 280;
        function settle(now2: number) {
          const u = Math.min(1, (now2 - t1) / settleDur);
          const hop = Math.sin(u * Math.PI) * 5;
          if (wrapRef.current) {
            wrapRef.current.style.transform = `translate(${end.x}px, ${end.y - hop}px)`;
          }
          if (u < 1) {
            animRef.current = requestAnimationFrame(settle);
          } else {
            if (wrapRef.current) {
              wrapRef.current.style.transform = `translate(${end.x}px, ${end.y}px)`;
            }
            posRef.current = end;
            setWalking(false);
            arriveRef.current?.(agentId);
          }
        }
        animRef.current = requestAnimationFrame(settle);
      }
    }
    animRef.current = requestAnimationFrame(frame);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      clearInterval(dustTimer);
      clearTimeout(initialDust);
    };
  }, [target.x, target.y, agentId]);

  const wrapClass = [
    'critter-wrap',
    walking ? 'walking' : '',
    state === 'thinking' ? 'thinking' : '',
    state === 'acting' ? 'acting' : '',
    !alive ? 'opacity-50 grayscale' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div ref={wrapRef} className={wrapClass}>
      {delta != null && (
        <div
          key={delta.key}
          className={`delta-float ${delta.amount >= 0 ? 'pos' : 'neg'}`}
        >
          {delta.amount >= 0 ? '+' : '−'}${Math.abs(delta.amount).toFixed(2)}
        </div>
      )}

      {bubble && (
        <div
          className={`bubble bubble-${bubble.kind}`}
          style={bubble.kind === 'intent' && bubble.tint ? { borderColor: bubble.tint } : undefined}
        >
          {bubble.kind === 'dots' && (
            <div className="bubble-dots">
              <span />
              <span />
              <span />
            </div>
          )}
          {bubble.kind === 'intent' && (
            <>
              <span className="bubble-emoji">{bubble.emoji}</span>
              <span className="bubble-text">{bubble.text}</span>
            </>
          )}
        </div>
      )}

      <div className="critter">
        <div className="critter-inner">
          <div className={`facing-flip ${facing < 0 ? 'left' : ''}`}>
            <div className="critter-legs">
              <div className="leg left" style={{ background: color }} />
              <div className="leg right" style={{ background: color }} />
            </div>
            <div className="critter-body" style={{ background: color }}>
              <div className="critter-face">
                <div className="eye left" />
                <div className="eye right" />
                <div className="mouth" />
                <div className="blush left" />
                <div className="blush right" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="critter-shadow" />

      {dust.map((d) => (
        <div
          key={d.id}
          className="dust"
          style={{ ['--dx' as unknown as string]: `${d.dx}px` } as React.CSSProperties}
        />
      ))}

      <div className="critter-name" style={{ borderColor: color }}>
        {name}
      </div>
      {showBalance && (
        <div className="critter-balance">${balance.toFixed(2)}</div>
      )}
    </div>
  );
}

// Small avatar — used in roster cards and the config panel.
export function CritterAvatar({
  color,
  size = 34,
  alive = true,
  className,
}: {
  color: string;
  size?: number;
  alive?: boolean;
  className?: string;
}) {
  const eyeTop = size * 0.32;
  const eyeOff = size * 0.26;
  return (
    <div
      className={className}
      style={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: '50% 50% 45% 45% / 60% 60% 40% 40%',
        background: color,
        boxShadow: 'inset 0 -3px 0 rgba(0,0,0,0.08)',
        opacity: alive ? 1 : 0.5,
        filter: alive ? undefined : 'grayscale(0.8)',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          left: eyeOff,
          top: eyeTop,
          width: size * 0.12,
          height: size * 0.16,
          borderRadius: '50%',
          background: '#2C2218',
        }}
      />
      <span
        style={{
          position: 'absolute',
          right: eyeOff,
          top: eyeTop,
          width: size * 0.12,
          height: size * 0.16,
          borderRadius: '50%',
          background: '#2C2218',
        }}
      />
    </div>
  );
}
