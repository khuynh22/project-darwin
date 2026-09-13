import { VENUES, type Venue } from '@/lib/town';

/** Half-extent of the ground plane in world units. */
export const GROUND = 26;

/**
 * The 2-D town is laid out in a 780x560 pixel stage. The 3-D view reuses those
 * coordinates rather than inventing a second layout, so a venue sits in the
 * same relative place in both views and the two are recognisably one world.
 */
export const STAGE_W = 780;
export const STAGE_H = 560;

export type Vec3 = [number, number, number];

/** Side length of a venue block, in world units. Shared so agent slots can be
 *  placed clear of it instead of guessing at its size. */
export const VENUE_FOOTPRINT = 5.2;

/** Stage pixel coordinates -> world units, centred on the origin. */
export function stageToWorld(x: number, y: number, height = 0): Vec3 {
  const scale = (GROUND * 2) / STAGE_W;
  return [(x - STAGE_W / 2) * scale, height, (y - STAGE_H / 2) * scale];
}

export function venuePosition(venue: Venue): Vec3 {
  return stageToWorld(venue.x, venue.y);
}

/**
 * Where an agent stands when it is at a venue.
 *
 * Agents at the same venue must not occupy the same point, or a turn where
 * everyone works reads as a single critter. Slots spiral outward so the
 * arrangement stays stable as the count changes -- an agent should not jump
 * across the plaza because a neighbour arrived.
 */
export function agentSlot(venue: Venue, index: number, total: number): Vec3 {
  const [x, , z] = venuePosition(venue);
  // Outside the block, not on it: a pawn within the footprint is drawn behind
  // the plinth and the roof slab, which hides the agent entirely.
  const inner = VENUE_FOOTPRINT / 2 + 1.0;
  if (total <= 1) return [x, 0, z + inner];
  const radius = inner + Math.floor(index / 6) * 1.3;
  const angle = (index % 6) * ((Math.PI * 2) / 6) + Math.PI / 2;
  return [x + Math.cos(angle) * radius, 0, z + Math.sin(angle) * radius];
}

/** Venue lookup that tolerates an unmapped id, mirroring `actionDef`. */
export function venueById(id: string | undefined): Venue {
  return VENUES.find((v) => v.id === id) ?? VENUES[0];
}

/**
 * Whether this browser can run the 3-D view.
 *
 * Checked before mounting a canvas rather than after: a WebGL failure inside
 * R3F surfaces as an opaque crash, and the 2-D gallery must stay reachable.
 */
export function hasWebGL(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    return Boolean(
      canvas.getContext('webgl2') ??
        canvas.getContext('webgl') ??
        canvas.getContext('experimental-webgl'),
    );
  } catch {
    return false;
  }
}
