import { VENUES } from '@/lib/town';
import { GROUND, VENUE_FOOTPRINT, venuePosition } from '@/lib/world3d';

/**
 * Standing in the town rather than looking down at it.
 *
 * World units are metres: the plaza is 52m across, a venue block is 5.2m wide,
 * and you are 1.7m tall. Keeping that honest is what makes the buildings read
 * as buildings and the agents read as people.
 *
 * All of this is pure. The controller component owns the camera and the clock;
 * everything that decides *where a body ends up* lives here, where it can be
 * tested without a browser.
 */

export const EYE_HEIGHT = 1.7;
export const WALK_SPEED = 4.5;
export const RUN_SPEED = 9;

/** Half-width of the walker, so you stop at a wall rather than inside it. */
export const BODY_RADIUS = 0.35;

export type Vec2 = [number, number];

export type Box = { minX: number; maxX: number; minZ: number; maxZ: number };

export type Keys = {
  forward: boolean;
  back: boolean;
  left: boolean;
  right: boolean;
};

/**
 * Ground-plane velocity for the keys held, in the direction the head faces.
 *
 * Normalised before scaling, or holding two keys walks you diagonally at 1.41x
 * — the oldest bug in first-person movement.
 */
export function walkVector(
  keys: Keys,
  yaw: number,
  speed: number,
  delta: number,
): { dx: number; dz: number } {
  const ahead = (keys.forward ? 1 : 0) - (keys.back ? 1 : 0);
  const side = (keys.right ? 1 : 0) - (keys.left ? 1 : 0);
  if (ahead === 0 && side === 0) return { dx: 0, dz: 0 };

  const sin = Math.sin(yaw);
  const cos = Math.cos(yaw);

  // Three.js convention: a camera at rest looks down -Z.
  let dx = ahead * -sin + side * cos;
  let dz = ahead * -cos + side * sin;

  const length = Math.hypot(dx, dz);
  dx = (dx / length) * speed * delta;
  dz = (dz / length) * speed * delta;
  return { dx, dz };
}

/** The venue blocks, grown by the walker's radius so a wall stops the body. */
export function venueBlockers(): Box[] {
  const half = VENUE_FOOTPRINT / 2 + BODY_RADIUS;
  return VENUES.map((venue) => {
    const [x, , z] = venuePosition(venue);
    return { minX: x - half, maxX: x + half, minZ: z - half, maxZ: z + half };
  });
}

function inside(box: Box, x: number, z: number): boolean {
  return x > box.minX && x < box.maxX && z > box.minZ && z < box.maxZ;
}

export function clampToWorld([x, z]: Vec2): Vec2 {
  const limit = GROUND - BODY_RADIUS;
  return [
    Math.max(-limit, Math.min(limit, x)),
    Math.max(-limit, Math.min(limit, z)),
  ];
}

/**
 * Where the body actually ends up this frame.
 *
 * Each axis is resolved on its own, so walking into a wall at an angle slides
 * along it instead of stopping dead — without that, every corner is flypaper.
 * A body that somehow starts inside a box is let out rather than trapped: a
 * stuck camera cannot be recovered without reloading the page.
 */
export function resolveMove(from: Vec2, to: Vec2, blockers: Box[]): Vec2 {
  const [fromX, fromZ] = from;
  const stuck = blockers.some((box) => inside(box, fromX, fromZ));
  if (stuck) return clampToWorld(to);

  const [wantX, wantZ] = to;
  let x = wantX;
  let z = fromZ;
  if (blockers.some((box) => inside(box, x, z))) x = fromX;

  z = wantZ;
  if (blockers.some((box) => inside(box, x, z))) z = fromZ;

  return clampToWorld([x, z]);
}
