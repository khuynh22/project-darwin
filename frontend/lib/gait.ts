/**
 * A body that walks like a person.
 *
 * Everything here is metres and radians, matching the rest of the world: the
 * eye height you view the town from is 1.7m, so an agent has to actually be
 * 1.7m or standing next to one reads wrong.
 *
 * The pose is a pure function of how far the body has walked, never of elapsed
 * time. Time-driven legs windmill while the body inches along, and scrape the
 * ground during a sprint.
 */

const HEIGHT = 1.7;
const HEAD_RADIUS = 0.115;
const LEG_LENGTH = 0.82;

export const BODY = {
  height: HEIGHT,
  headRadius: HEAD_RADIUS,
  legLength: LEG_LENGTH,
  torsoHeight: HEIGHT - LEG_LENGTH - HEAD_RADIUS * 2,
  /** Shoulder to fingertip: past the hip, well short of the knee. */
  armLength: 0.56,
  shoulderWidth: 0.19,
  hipWidth: 0.105,
  limbRadius: 0.052,
  torsoWidth: 0.185,
  torsoDepth: 0.115,
} as const;

/** Metres covered by one step. One full cycle is two steps. */
export const STRIDE = 0.78;

export const SWING_AMPLITUDE = { leg: 0.62, arm: 0.42 } as const;

const BOB = 0.022;

export type Limb = 'leftLeg' | 'rightLeg' | 'leftArm' | 'rightArm';

/**
 * Half a cycle apart for the paired limb, and each arm in step with the leg on
 * the other side — contralateral, the way people actually walk. Same-side arm
 * and leg together reads as a marionette.
 */
const PHASE_OFFSET: Record<Limb, number> = {
  leftLeg: 0,
  rightLeg: Math.PI,
  leftArm: Math.PI,
  rightArm: 0,
};

export function limbAngle(phase: number, limb: Limb): number {
  const amplitude = limb.endsWith('Leg') ? SWING_AMPLITUDE.leg : SWING_AMPLITUDE.arm;
  return Math.sin(phase + PHASE_OFFSET[limb]) * amplitude;
}

/** Wrapped, because unbounded growth loses precision over a long run. */
export function advancePhase(phase: number, distance: number): number {
  if (distance === 0) return phase;
  const next = phase + (distance / STRIDE) * Math.PI;
  return ((next % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
}

/** Lowest at each footfall, highest as the legs pass — twice per cycle. */
export function bobHeight(phase: number): number {
  return Math.abs(Math.sin(phase)) * BOB;
}
