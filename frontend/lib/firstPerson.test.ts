import { describe, expect, it } from 'vitest';
import {
  BODY_RADIUS,
  WALK_SPEED,
  clampToWorld,
  resolveMove,
  venueBlockers,
  walkVector,
  walkVelocity,
  smoothVelocity,
  step,
  STOPPED,
  type Box,
} from '@/lib/firstPerson';
import { VENUES } from '@/lib/town';
import { GROUND, VENUE_FOOTPRINT, venuePosition } from '@/lib/world3d';

const NONE = { forward: false, back: false, left: false, right: false };
// `+ 0` normalises -0, which a quarter-turn produces and toBe distinguishes.
const round = (n: number) => Math.round(n * 1e6) / 1e6 + 0;

describe('walkVector', () => {
  it('walks towards -Z at rest yaw, which is where the camera looks', () => {
    const { dx, dz } = walkVector({ ...NONE, forward: true }, 0, WALK_SPEED, 1);
    expect(round(dx)).toBe(0);
    expect(round(dz)).toBe(-WALK_SPEED);
  });

  it('turns with the head', () => {
    // Yawed a quarter turn, "forward" is -X.
    const { dx, dz } = walkVector({ ...NONE, forward: true }, Math.PI / 2, WALK_SPEED, 1);
    expect(round(dx)).toBe(-WALK_SPEED);
    expect(round(dz)).toBe(0);
  });

  it('strafes at a right angle to the look direction', () => {
    const { dx, dz } = walkVector({ ...NONE, right: true }, 0, WALK_SPEED, 1);
    expect(round(dx)).toBe(WALK_SPEED);
    expect(round(dz)).toBe(0);
  });

  it('does not make diagonals faster', () => {
    // The classic bug: forward+right adds two full-speed vectors and you walk
    // 1.41x faster sideways than straight ahead.
    const straight = walkVector({ ...NONE, forward: true }, 0, WALK_SPEED, 1);
    const diagonal = walkVector({ ...NONE, forward: true, right: true }, 0, WALK_SPEED, 1);
    const speed = (v: { dx: number; dz: number }) => Math.hypot(v.dx, v.dz);
    expect(round(speed(diagonal))).toBe(round(speed(straight)));
  });

  it('scales with the frame time, so speed is per second and not per frame', () => {
    const half = walkVector({ ...NONE, forward: true }, 0, WALK_SPEED, 0.5);
    expect(round(half.dz)).toBe(round(-WALK_SPEED / 2));
  });

  it('stands still with nothing held, and with opposite keys held', () => {
    expect(walkVector(NONE, 0, WALK_SPEED, 1)).toEqual({ dx: 0, dz: 0 });
    const both = walkVector({ ...NONE, forward: true, back: true }, 0, WALK_SPEED, 1);
    expect(round(both.dx)).toBe(0);
    expect(round(both.dz)).toBe(0);
  });
});

describe('venueBlockers', () => {
  it('gives one box per venue, sized to the block plus the walker', () => {
    const boxes = venueBlockers();
    expect(boxes).toHaveLength(VENUES.length);

    const [vx, , vz] = venuePosition(VENUES[0]);
    const box = boxes[0];
    const half = VENUE_FOOTPRINT / 2 + BODY_RADIUS;
    expect(round(box.minX)).toBe(round(vx - half));
    expect(round(box.maxZ)).toBe(round(vz + half));
  });
});

describe('resolveMove', () => {
  const box: Box = { minX: -1, maxX: 1, minZ: -1, maxZ: 1 };

  it('lets you walk in the open', () => {
    expect(resolveMove([10, 10], [11, 10], [box])).toEqual([11, 10]);
  });

  it('stops you walking into a building', () => {
    const [x, z] = resolveMove([-3, 0], [-0.5, 0], [box]);
    expect(x).toBe(-3);
    expect(z).toBe(0);
  });

  it('slides you along a wall instead of gluing you to it', () => {
    // Pushing into the west face while also heading north: the blocked axis is
    // dropped, the free one is kept. Without this you stick on every corner.
    const [x, z] = resolveMove([-3, 0], [-0.5, 2], [box]);
    expect(x).toBe(-3);
    expect(z).toBe(2);
  });

  it('does not trap someone who is already inside a box', () => {
    // Should never happen, but a stuck camera is unrecoverable without a reload.
    expect(resolveMove([0, 0], [0.5, 0], [box])).toEqual([0.5, 0]);
  });

  it('keeps you on the ground plane', () => {
    const far = GROUND * 4;
    const [x, z] = clampToWorld([far, -far]);
    expect(x).toBeLessThanOrEqual(GROUND);
    expect(z).toBeGreaterThanOrEqual(-GROUND);
  });

  it('leaves a walkable gap between neighbouring venues', () => {
    // If the blockers overlap there is no way through the middle of town, and
    // the whole point is walking up to an agent.
    const boxes = venueBlockers();
    const overlapping = boxes.some((a, i) =>
      boxes.some(
        (b, j) =>
          i !== j &&
          a.minX < b.maxX &&
          a.maxX > b.minX &&
          a.minZ < b.maxZ &&
          a.maxZ > b.minZ,
      ),
    );
    expect(overlapping).toBe(false);
  });
});

describe('smoothVelocity', () => {
  const FULL = { dx: WALK_SPEED, dz: 0 };

  it('ramps toward the target instead of jumping to it', () => {
    const first = smoothVelocity(STOPPED, FULL, 1 / 60);
    expect(first.dx).toBeGreaterThan(0);
    expect(first.dx).toBeLessThan(FULL.dx);
  });

  it('coasts to a stop rather than stopping dead', () => {
    const coasting = smoothVelocity(FULL, STOPPED, 1 / 60);
    expect(coasting.dx).toBeGreaterThan(0);
    expect(coasting.dx).toBeLessThan(FULL.dx);
  });

  it('settles exactly, so a stopped camera does not creep', () => {
    let v = FULL;
    for (let i = 0; i < 600; i += 1) v = smoothVelocity(v, STOPPED, 1 / 60);
    expect(v).toEqual(STOPPED);
  });

  it('covers the same ground per second at any frame rate', () => {
    // A fixed per-frame fraction would ramp twice as fast at 120fps, so the
    // same key press would move you further on a faster machine.
    const travel = (fps: number) => {
      let v = STOPPED;
      let distance = 0;
      for (let i = 0; i < fps; i += 1) {
        v = smoothVelocity(v, FULL, 1 / fps);
        distance += step(v, 1 / fps).dx;
      }
      return distance;
    };
    // Not exact: summing a continuous ramp at different step sizes leaves a
    // discretisation residue. Within a couple of percent is the real claim.
    const slow = travel(30);
    expect(Math.abs(travel(120) - slow) / slow).toBeLessThan(0.02);
  });

  it('reaches practically full speed within a few frames', () => {
    let v = STOPPED;
    for (let i = 0; i < 12; i += 1) v = smoothVelocity(v, FULL, 1 / 60);
    expect(v.dx).toBeGreaterThan(WALK_SPEED * 0.9);
  });
});

describe('strafing at any heading', () => {
  const headings = [0.3, Math.PI / 4, Math.PI / 2, 2.2, Math.PI, -1.1];

  it('stays at a right angle to where you are looking', () => {
    for (const yaw of headings) {
      const ahead = walkVelocity({ ...NONE, forward: true }, yaw, WALK_SPEED);
      const side = walkVelocity({ ...NONE, right: true }, yaw, WALK_SPEED);
      expect(ahead.dx * side.dx + ahead.dz * side.dz, `yaw ${yaw}`).toBeCloseTo(0, 6);
    }
  });

  it('puts right on the right: forward turned clockwise seen from above', () => {
    for (const yaw of headings) {
      const ahead = walkVelocity({ ...NONE, forward: true }, yaw, WALK_SPEED);
      const side = walkVelocity({ ...NONE, right: true }, yaw, WALK_SPEED);
      // right = forward x up, so forward x right = -up: its y component,
      // fz*rx - fx*rz, is negative whenever right is on the right.
      expect(ahead.dz * side.dx - ahead.dx * side.dz, `yaw ${yaw}`).toBeLessThan(0);
    }
  });
});
