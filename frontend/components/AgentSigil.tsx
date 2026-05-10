'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { useId } from 'react';

export type SigilState = 'idle' | 'thinking' | 'walking';

interface AgentSigilProps {
  color: string;
  size?: number;
  state?: SigilState;
  alive?: boolean;
  className?: string;
}

// Two orbital rings, counter-rotating, at different radii.
const OUTER_PARTICLES = [
  { phaseDeg: 0, period: 9 },
  { phaseDeg: 120, period: 9 },
  { phaseDeg: 240, period: 9 },
];
const INNER_PARTICLES = [
  { phaseDeg: 60, period: 6 },
  { phaseDeg: 180, period: 6 },
  { phaseDeg: 300, period: 6 },
];

// Three radial spokes that ping outward.
const SPOKES = [0, 120, 240];

const HEX_POINTS = '50,16 76,32 76,64 50,80 24,64 24,32';

// Tick marks at hex vertices on the outer ring.
const TICK_MARKS = [0, 60, 120, 180, 240, 300];

export default function AgentSigil({
  color,
  size = 56,
  state = 'idle',
  alive = true,
  className,
}: AgentSigilProps) {
  const gradientId = useId();
  const reduce = useReducedMotion();

  // Speed multipliers — smaller = faster.
  const speedScale = state === 'thinking' ? 0.45 : state === 'walking' ? 0.55 : 1;
  const pulsePeriod = state === 'thinking' ? 0.85 : state === 'walking' ? 1.0 : 1.7;
  const glowBase = state === 'thinking' ? 0.75 : state === 'walking' ? 0.6 : 0.42;
  const coreScale =
    state === 'thinking' ? [1, 1.22, 1] : state === 'walking' ? [1, 1.12, 1] : [1, 1.08, 1];
  const spokeMaxScale = state === 'thinking' ? 1.6 : 1.35;

  if (!alive) {
    return (
      <svg
        className={className}
        width={size}
        height={size}
        viewBox="0 0 100 100"
        aria-hidden="true"
      >
        <circle cx={50} cy={50} r={18} fill={color} opacity={0.12} />
        <line x1={34} y1={34} x2={66} y2={66} stroke={color} strokeOpacity={0.45} strokeWidth={2} strokeLinecap="round" />
        <line x1={66} y1={34} x2={34} y2={66} stroke={color} strokeOpacity={0.45} strokeWidth={2} strokeLinecap="round" />
      </svg>
    );
  }

  // Reduced-motion: render a static, layered sigil — no infinite animations.
  if (reduce) {
    return (
      <svg
        className={className}
        width={size}
        height={size}
        viewBox="0 0 100 100"
        style={{ overflow: 'visible' }}
        aria-hidden="true"
      >
        <defs>
          <radialGradient id={gradientId}>
            <stop offset="0%" stopColor={color} stopOpacity={0.6} />
            <stop offset="60%" stopColor={color} stopOpacity={0.18} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </radialGradient>
        </defs>
        <circle cx={50} cy={50} r={45} fill={`url(#${gradientId})`} opacity={glowBase} />
        <circle cx={50} cy={50} r={42} fill="none" stroke={color} strokeOpacity={0.25} strokeWidth={0.6} strokeDasharray="2 2" />
        <polygon points={HEX_POINTS} fill="none" stroke={color} strokeOpacity={0.5} strokeWidth={1} />
        <circle cx={50} cy={50} r={26} fill="none" stroke={color} strokeOpacity={0.25} strokeWidth={0.7} strokeDasharray="3 4" />
        <circle cx={50} cy={50} r={12} fill={color} />
        <circle cx={50} cy={50} r={5.5} fill="white" opacity={0.85} />
        {OUTER_PARTICLES.concat(INNER_PARTICLES).map((p, i) => {
          const angle = (p.phaseDeg * Math.PI) / 180;
          const r = i < 3 ? 23 : 15;
          return (
            <circle
              key={i}
              cx={50 + Math.cos(angle) * r}
              cy={50 + Math.sin(angle) * r}
              r={2}
              fill={color}
            />
          );
        })}
      </svg>
    );
  }

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      style={{ overflow: 'visible' }}
      aria-hidden="true"
    >
      <defs>
        <radialGradient id={gradientId}>
          <stop offset="0%" stopColor={color} stopOpacity={0.6} />
          <stop offset="60%" stopColor={color} stopOpacity={0.18} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </radialGradient>
      </defs>

      {/* Outer halo — breathing */}
      <motion.circle
        cx={50}
        cy={50}
        r={45}
        fill={`url(#${gradientId})`}
        animate={{ opacity: [glowBase * 0.6, glowBase, glowBase * 0.6] }}
        transition={{ duration: pulsePeriod * 1.4, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Outer dashed ring with tick marks — counter-rotates slowly */}
      <motion.g
        animate={{ rotate: -360 }}
        transition={{ duration: 30 * speedScale, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: '50px 50px' }}
      >
        <circle
          cx={50}
          cy={50}
          r={42}
          fill="none"
          stroke={color}
          strokeOpacity={0.28}
          strokeWidth={0.6}
          strokeDasharray="2 2"
        />
        {TICK_MARKS.map((deg) => {
          const a = (deg * Math.PI) / 180;
          const x1 = 50 + Math.cos(a) * 39;
          const y1 = 50 + Math.sin(a) * 39;
          const x2 = 50 + Math.cos(a) * 44;
          const y2 = 50 + Math.sin(a) * 44;
          return (
            <line
              key={deg}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={color}
              strokeOpacity={0.5}
              strokeWidth={0.7}
            />
          );
        })}
      </motion.g>

      {/* Hex frame — rotates clockwise */}
      <motion.polygon
        points={HEX_POINTS}
        fill="none"
        stroke={color}
        strokeOpacity={0.55}
        strokeWidth={1}
        animate={{ rotate: 360 }}
        transition={{ duration: 22 * speedScale, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: '50px 50px' }}
      />

      {/* Inner dashed ring — counter-rotates */}
      <motion.circle
        cx={50}
        cy={50}
        r={26}
        fill="none"
        stroke={color}
        strokeOpacity={0.3}
        strokeWidth={0.7}
        strokeDasharray="3 4"
        animate={{ rotate: -360 }}
        transition={{ duration: 14 * speedScale, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: '50px 50px' }}
      />

      {/* Pulsing radial spokes — three short rays */}
      {SPOKES.map((deg) => {
        const a = (deg * Math.PI) / 180;
        const x2 = 50 + Math.cos(a) * 19;
        const y2 = 50 + Math.sin(a) * 19;
        return (
          <motion.line
            key={deg}
            x1={50}
            y1={50}
            x2={x2}
            y2={y2}
            stroke={color}
            strokeOpacity={0.6}
            strokeWidth={1}
            strokeLinecap="round"
            animate={{
              opacity: [0, 0.8, 0],
              pathLength: [0.3, spokeMaxScale, 0.3],
            }}
            transition={{
              duration: pulsePeriod * 1.6,
              repeat: Infinity,
              ease: 'easeOut',
              delay: (deg / 360) * pulsePeriod,
            }}
            style={{ transformOrigin: '50px 50px' }}
          />
        );
      })}

      {/* Sweeping scanline across the body */}
      <motion.line
        x1={50}
        y1={30}
        x2={50}
        y2={70}
        stroke={color}
        strokeOpacity={0.45}
        strokeWidth={0.9}
        strokeLinecap="round"
        animate={{ rotate: 360 }}
        transition={{ duration: 11 * speedScale, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: '50px 50px' }}
      />

      {/* Core */}
      <motion.circle
        cx={50}
        cy={50}
        r={12}
        fill={color}
        animate={{ scale: coreScale }}
        transition={{ duration: pulsePeriod, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '50px 50px' }}
      />

      {/* Inner highlight */}
      <motion.circle
        cx={50}
        cy={50}
        r={5.5}
        fill="white"
        opacity={0.9}
        animate={{ scale: state === 'thinking' ? [0.85, 1.2, 0.85] : [0.95, 1.08, 0.95] }}
        transition={{ duration: pulsePeriod * 0.7, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '50px 50px' }}
      />

      {/* Outer orbital ring */}
      {OUTER_PARTICLES.map((p, i) => (
        <motion.g
          key={`o${i}`}
          initial={{ rotate: p.phaseDeg }}
          animate={{ rotate: p.phaseDeg + 360 }}
          transition={{ duration: p.period * speedScale, repeat: Infinity, ease: 'linear' }}
          style={{ transformOrigin: '50px 50px' }}
        >
          <circle cx={50 + 23} cy={50} r={2.2} fill={color} />
        </motion.g>
      ))}

      {/* Inner orbital ring (counter-rotates) */}
      {INNER_PARTICLES.map((p, i) => (
        <motion.g
          key={`i${i}`}
          initial={{ rotate: p.phaseDeg }}
          animate={{ rotate: p.phaseDeg - 360 }}
          transition={{ duration: p.period * speedScale, repeat: Infinity, ease: 'linear' }}
          style={{ transformOrigin: '50px 50px' }}
        >
          <circle cx={50 + 15} cy={50} r={1.6} fill={color} opacity={0.85} />
        </motion.g>
      ))}
    </svg>
  );
}
