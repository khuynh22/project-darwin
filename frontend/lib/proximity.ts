import type { Venue } from '@/lib/town';
import { VENUE_FOOTPRINT, venuePosition, type Vec3 } from '@/lib/world3d';

/**
 * Who you are close enough to, and facing, to be reading.
 *
 * On foot there is no clicking: you find out what an agent is doing by walking
 * over and looking at it. That makes "who is in front of me" the selection
 * mechanism, so it has to be steady — a panel that swaps between two agents as
 * you breathe is worse than no panel.
 */

/** Metres. Roughly "close enough to be talking to them". */
export const FOCUS_RADIUS = 9;

/**
 * Cosine of the half-angle you count as looking at someone: ~70°, so an agent
 * near the edge of the screen still reads, but one beside you does not.
 */
export const FOCUS_MIN_DOT = 0.35;

/**
 * How much further you may drift before losing whoever you are already
 * reading. Without the slack, standing at exactly the edge strobes the panel.
 */
const KEEP_MARGIN = 1.25;

export type Locatable = { agentId: string; position: Vec3 };

/**
 * Lower is "more the one you mean". Distance divided by how centred they are,
 * so a body filling your view beats one closer but off to the side — walking
 * into a crowd and reading whoever is nearest describes someone who is not the
 * one you are looking at.
 */
function score(
  eye: Vec3,
  look: Vec3,
  agent: Locatable,
  radius: number,
): number | null {
  const dx = agent.position[0] - eye[0];
  const dz = agent.position[2] - eye[2];
  const distance = Math.hypot(dx, dz);
  if (distance > radius) return null;
  if (distance < 1e-6) return 0;

  const lookLength = Math.hypot(look[0], look[2]);
  if (lookLength < 1e-6) return null;
  const dot = (dx * look[0] + dz * look[2]) / (distance * lookLength);
  if (dot < FOCUS_MIN_DOT) return null;
  return distance / dot;
}

/** Metres. A building is read from outside it, so the radius clears its own
 *  footprint before the six metres of approach. */
export const VENUE_FOCUS_RADIUS = VENUE_FOOTPRINT / 2 + 6;

function focusAmong(
  eye: Vec3,
  look: Vec3,
  agents: Locatable[],
  current: string | null,
  radius: number,
): string | null {
  if (current) {
    const held = agents.find((a) => a.agentId === current);
    if (held && score(eye, look, held, radius * KEEP_MARGIN) !== null) {
      return current;
    }
  }

  let best: { id: string; score: number } | null = null;
  for (const agent of agents) {
    const value = score(eye, look, agent, radius);
    if (value === null) continue;
    // Ties broken by id so the same crowd always yields the same answer,
    // whatever order the frame happened to list them in.
    if (
      best === null ||
      value < best.score ||
      (value === best.score && agent.agentId < best.id)
    ) {
      best = { id: agent.agentId, score: value };
    }
  }
  return best?.id ?? null;
}

export function focusTarget(
  eye: Vec3,
  look: Vec3,
  agents: Locatable[],
  current: string | null,
): string | null {
  return focusAmong(eye, look, agents, current, FOCUS_RADIUS);
}

/**
 * Which building you are standing at.
 *
 * Same rule as reading an agent -- walk over and look at it -- so the two share
 * the scoring and differ only in how close counts as close.
 */
export function focusVenue(
  eye: Vec3,
  look: Vec3,
  venues: Venue[],
  current: string | null,
): string | null {
  const located = venues.map((venue) => ({
    agentId: venue.id,
    position: venuePosition(venue),
  }));
  return focusAmong(eye, look, located, current, VENUE_FOCUS_RADIUS);
}
