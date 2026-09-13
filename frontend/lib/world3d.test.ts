import { describe, expect, it } from 'vitest';
import { VENUES } from '@/lib/town';
import { VENUE_FOOTPRINT, agentSlot, venuePosition } from '@/lib/world3d';

describe('agentSlot', () => {
  const venue = VENUES[0];

  it('stands every agent clear of the venue block', () => {
    // A pawn inside the plinth footprint is drawn behind it, and an agent you
    // cannot see is a view that does not say where anyone is.
    const [vx, , vz] = venuePosition(venue);
    for (const total of [1, 2, 6, 10]) {
      for (let i = 0; i < total; i++) {
        const [x, , z] = agentSlot(venue, i, total);
        const clearance = Math.max(Math.abs(x - vx), Math.abs(z - vz));
        expect(clearance, `slot ${i} of ${total}`).toBeGreaterThan(
          VENUE_FOOTPRINT / 2,
        );
      }
    }
  });

  it('gives each occupant its own spot', () => {
    const seen = new Set(
      Array.from({ length: 10 }, (_, i) => agentSlot(venue, i, 10).join(',')),
    );
    expect(seen.size).toBe(10);
  });

  it('does not move an agent when a neighbour arrives', () => {
    // Slots are indexed, not packed, so an agent keeps its spot as the crowd
    // grows. Otherwise everyone jumps across the plaza every turn.
    expect(agentSlot(venue, 0, 2)).toEqual(agentSlot(venue, 0, 5));
  });
});
