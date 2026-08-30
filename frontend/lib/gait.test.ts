import { describe, expect, it } from 'vitest';
import {
  BODY,
  STRIDE,
  SWING_AMPLITUDE,
  advancePhase,
  bobHeight,
  limbAngle,
} from '@/lib/gait';

const round = (n: number) => Math.round(n * 1e6) / 1e6 + 0;

describe('BODY proportions', () => {
  it('adds up to the height the rest of the world assumes', () => {
    // firstPerson.EYE_HEIGHT and the venue scale are all in metres; a body that
    // does not actually reach 1.7m makes the town read wrong from the ground.
    const stacked = BODY.legLength + BODY.torsoHeight + BODY.headRadius * 2;
    expect(round(stacked)).toBe(round(BODY.height));
  });

  it('is roughly seven and a half heads tall, like a person', () => {
    const heads = BODY.height / (BODY.headRadius * 2);
    expect(heads).toBeGreaterThan(6.5);
    expect(heads).toBeLessThan(8.5);
  });

  it('has arms that reach past the hips but not the knees', () => {
    const hipHeight = BODY.legLength;
    const shoulderHeight = BODY.legLength + BODY.torsoHeight * 0.86;
    const fingertips = shoulderHeight - BODY.armLength;
    expect(fingertips).toBeLessThan(hipHeight);
    expect(fingertips).toBeGreaterThan(hipHeight * 0.5);
  });
});

describe('limbAngle', () => {
  it('swings the legs in opposition', () => {
    // Both legs forward at once is a bunny hop, not a walk.
    for (const phase of [0, 0.7, 1.9, 4.2]) {
      expect(round(limbAngle(phase, 'leftLeg'))).toBe(
        round(-limbAngle(phase, 'rightLeg')),
      );
    }
  });

  it('swings each arm with the opposite leg', () => {
    // Contralateral, the way people actually walk. Same-side arm and leg
    // together reads as a marionette. Arms swing less far than legs, so this
    // is about direction, not magnitude.
    const direction = (n: number) => Math.sign(round(n));
    for (const phase of [0.7, 1.9, 4.2, 5.5]) {
      expect(direction(limbAngle(phase, 'leftArm'))).toBe(
        direction(limbAngle(phase, 'rightLeg')),
      );
      expect(direction(limbAngle(phase, 'rightArm'))).toBe(
        direction(limbAngle(phase, 'leftLeg')),
      );
      expect(direction(limbAngle(phase, 'leftArm'))).not.toBe(
        direction(limbAngle(phase, 'leftLeg')),
      );
    }
  });

  it('never swings further than the amplitude', () => {
    for (let phase = 0; phase < Math.PI * 4; phase += 0.13) {
      expect(Math.abs(limbAngle(phase, 'leftLeg'))).toBeLessThanOrEqual(
        SWING_AMPLITUDE.leg + 1e-9,
      );
      expect(Math.abs(limbAngle(phase, 'leftArm'))).toBeLessThanOrEqual(
        SWING_AMPLITUDE.arm + 1e-9,
      );
    }
  });

  it('swings the legs further than the arms', () => {
    expect(SWING_AMPLITUDE.leg).toBeGreaterThan(SWING_AMPLITUDE.arm);
  });
});

describe('advancePhase', () => {
  it('is driven by distance walked, not by time', () => {
    // Phase from elapsed time means the legs windmill while the body inches
    // along, or scrape the ground during a sprint.
    expect(advancePhase(0, STRIDE)).toBe(Math.PI);
    expect(round(advancePhase(0, STRIDE / 2))).toBe(round(Math.PI / 2));
  });

  it('returns to the same pose after a full cycle', () => {
    expect(round(advancePhase(0, STRIDE * 2))).toBe(0);
  });

  it('does not move while standing still', () => {
    expect(advancePhase(1.23, 0)).toBe(1.23);
  });

  it('stays inside one turn of the circle however far you walk', () => {
    // Unbounded growth loses float precision after a long run and the gait
    // starts to stutter.
    const far = advancePhase(0, STRIDE * 1000);
    expect(far).toBeGreaterThanOrEqual(0);
    expect(far).toBeLessThan(Math.PI * 2);
  });
});

describe('bobHeight', () => {
  it('is lowest at the step and highest as the legs pass', () => {
    expect(round(bobHeight(0))).toBe(0);
    expect(bobHeight(Math.PI / 2)).toBeGreaterThan(0);
  });

  it('rises and falls twice per stride cycle, one per footfall', () => {
    expect(round(bobHeight(0))).toBe(round(bobHeight(Math.PI)));
    expect(round(bobHeight(Math.PI / 2))).toBe(round(bobHeight((3 * Math.PI) / 2)));
  });

  it('never goes negative, so nobody sinks into the ground', () => {
    for (let phase = 0; phase < Math.PI * 4; phase += 0.11) {
      expect(bobHeight(phase)).toBeGreaterThanOrEqual(0);
    }
  });
});
