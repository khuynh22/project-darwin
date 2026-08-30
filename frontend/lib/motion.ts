import type { Vec3 } from '@/lib/world3d';

/**
 * Getting an agent from where it was to where it is.
 *
 * The trace says where an agent stood on turn N and on turn N+1, and nothing
 * about the space between. Walking that gap is a rendering choice, not a claim
 * about the world: nothing here feeds a measurement, and an agent's position at
 * a turn is still exactly what the trace recorded.
 */

/** Metres per second, before the bounds below take over. */
const WALK_SPEED = 7;

export const MIN_WALK_SECONDS = 0.35;

/**
 * Bounded above so a walk cannot outlive the turn that caused it — replay
 * playback advances every 700ms and an agent still crossing the plaza from two
 * turns ago is a lie about where it is.
 */
export const MAX_WALK_SECONDS = 1.6;

export function easeInOutCubic(t: number): number {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

export function lerp3(from: Vec3, to: Vec3, t: number): Vec3 {
  return [
    from[0] + (to[0] - from[0]) * t,
    from[1] + (to[1] - from[1]) * t,
    from[2] + (to[2] - from[2]) * t,
  ];
}

export function distance3(from: Vec3, to: Vec3): number {
  return Math.hypot(to[0] - from[0], to[1] - from[1], to[2] - from[2]);
}

export function walkDuration(from: Vec3, to: Vec3): number {
  const seconds = distance3(from, to) / WALK_SPEED;
  return Math.max(MIN_WALK_SECONDS, Math.min(MAX_WALK_SECONDS, seconds));
}

/**
 * Which way to face while walking, keeping the current facing when still.
 *
 * Without the standstill case an agent snaps to face north the moment it stops,
 * which is the one frame you are most likely to be looking at it.
 */
export function facingAngle(from: Vec3, to: Vec3, current: number): number {
  const dx = to[0] - from[0];
  const dz = to[2] - from[2];
  if (Math.hypot(dx, dz) < 1e-4) return current;
  return Math.atan2(dx, -dz);
}
