import { describe, expect, it } from 'vitest';
import {
  MAX_WALK_SECONDS,
  MIN_WALK_SECONDS,
  easeInOutCubic,
  facingAngle,
  lerp3,
  walkDuration,
} from '@/lib/motion';
import type { Vec3 } from '@/lib/world3d';

const A: Vec3 = [0, 0, 0];
const B: Vec3 = [10, 0, -20];

describe('easeInOutCubic', () => {
  it('starts at the start and ends exactly at the end', () => {
    // A walk that asymptotically approaches its destination never arrives, and
    // the agent spends the rest of the turn drifting by a millimetre.
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(1)).toBe(1);
  });

  it('clamps rather than overshooting', () => {
    expect(easeInOutCubic(-0.5)).toBe(0);
    expect(easeInOutCubic(1.5)).toBe(1);
  });

  it('never goes backwards', () => {
    let previous = -1;
    for (let t = 0; t <= 1.0001; t += 0.05) {
      const value = easeInOutCubic(t);
      expect(value).toBeGreaterThanOrEqual(previous);
      previous = value;
    }
  });
});

describe('lerp3', () => {
  it('lands on each end', () => {
    expect(lerp3(A, B, 0)).toEqual(A);
    expect(lerp3(A, B, 1)).toEqual(B);
  });

  it('is halfway at halfway', () => {
    expect(lerp3(A, B, 0.5)).toEqual([5, 0, -10]);
  });
});

describe('walkDuration', () => {
  it('takes longer to cross the plaza than to shuffle sideways', () => {
    expect(walkDuration(A, B)).toBeGreaterThan(walkDuration(A, [1, 0, 0]));
  });

  it('stays inside its bounds however far the trip', () => {
    // Bounded above so a walk cannot outlast the turn that caused it, and
    // below so a short step is not an instant snap.
    expect(walkDuration(A, [500, 0, 500])).toBe(MAX_WALK_SECONDS);
    expect(walkDuration(A, [0.01, 0, 0])).toBe(MIN_WALK_SECONDS);
  });
});

describe('facingAngle', () => {
  it('faces the way it is walking', () => {
    // The body faces +Z, so yaw 0 is +Z and walking -Z is a half turn.
    expect(facingAngle(A, [0, 0, 5], 42)).toBeCloseTo(0);
    expect(facingAngle(A, [0, 0, -5], 42)).toBeCloseTo(Math.PI);
    expect(facingAngle(A, [5, 0, 0], 42)).toBeCloseTo(Math.PI / 2);
    expect(facingAngle(A, [-5, 0, 0], 42)).toBeCloseTo(-Math.PI / 2);
  });

  it('faces the camera when it has never moved', () => {
    // The overview camera sits at +Z, so a resting agent at yaw 0 shows its
    // face rather than the back of its head.
    expect(facingAngle(A, A, 0)).toBe(0);
  });

  it('keeps the current facing when standing still', () => {
    // Otherwise an agent snaps to face north the instant it stops.
    expect(facingAngle(A, A, 1.23)).toBe(1.23);
  });
});
