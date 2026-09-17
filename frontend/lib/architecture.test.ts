import { describe, expect, it } from 'vitest';
import { VENUE_ROWS } from '@/lib/worldData';
import {
  DOOR,
  WALL,
  facadeFor,
  facadeExtent,
  hipConeRadius,
  windowGrid,
} from '@/lib/architecture';
import { VENUES } from '@/lib/town';
import { VENUE_FOOTPRINT } from '@/lib/world3d';

describe('facadeExtent', () => {
  it('never grows past the box you collide with', () => {
    // The walker is stopped by VENUE_FOOTPRINT. A building wider than that has
    // eaves you walk through, which is worse than no eaves.
    for (const venue of VENUES) {
      const extent = facadeExtent(facadeFor(venue.id));
      expect(extent.width, venue.id).toBeLessThanOrEqual(VENUE_FOOTPRINT);
      expect(extent.depth, venue.id).toBeLessThanOrEqual(VENUE_FOOTPRINT);
    }
  });

  it('keeps a pyramid roof inside the footprint too', () => {
    // A four-sided cone's base is a diamond of vertices at `radius`; turned to
    // line up with the walls it spans radius * sqrt(2). Sizing it by eye
    // overhangs the collision box, and eaves you walk through are worse than
    // no eaves.
    for (const venue of VENUES) {
      const facade = facadeFor(venue.id);
      if (facade.roof !== 'hip') continue;
      const span = hipConeRadius(facadeExtent(facade).width) * Math.SQRT2;
      expect(span, venue.id).toBeLessThanOrEqual(VENUE_FOOTPRINT + 1e-9);
    }
  });

  it('stays tall enough to look up at and short enough to see over the town', () => {
    for (const venue of VENUES) {
      const { height } = facadeExtent(facadeFor(venue.id));
      expect(height, venue.id).toBeGreaterThan(2.6);
      expect(height, venue.id).toBeLessThan(9);
    }
  });
});

describe('facadeFor', () => {
  it('gives the same building for the same venue every time', () => {
    expect(facadeFor('bank')).toEqual(facadeFor('bank'));
  });

  it('makes the six venues tell each other apart', () => {
    // A town of six identical sheds is not a town you can navigate.
    const shapes = VENUES.map((v) => JSON.stringify(facadeFor(v.id)));
    expect(new Set(shapes).size).toBe(VENUES.length);
  });

  it('falls back to something buildable for a venue it has never heard of', () => {
    const unknown = facadeFor('teleport-pad');
    expect(unknown.storeys).toBeGreaterThan(0);
    expect(facadeExtent(unknown).width).toBeLessThanOrEqual(VENUE_FOOTPRINT);
  });
});

describe('windowGrid', () => {
  const facade = facadeFor('bank');

  it('places exactly the windows it says it has', () => {
    expect(windowGrid(facade)).toHaveLength(facade.windowCols * facade.windowRows);
  });

  it('keeps every window on the wall', () => {
    for (const w of windowGrid(facade)) {
      expect(Math.abs(w.x) + w.width / 2).toBeLessThanOrEqual(WALL / 2);
      expect(w.y - w.height / 2).toBeGreaterThan(0);
      expect(w.y + w.height / 2).toBeLessThan(facadeExtent(facade).wallHeight);
    }
  });

  it('never puts a window where the door is', () => {
    // A window across the doorway is the kind of thing you only notice from
    // the ground, which is now where people stand.
    for (const w of windowGrid(facade)) {
      const overlapsX = Math.abs(w.x) - w.width / 2 < DOOR.width / 2;
      const overlapsY = w.y - w.height / 2 < DOOR.height;
      expect(overlapsX && overlapsY).toBe(false);
    }
  });

  it('is symmetric about the doorway', () => {
    const xs = windowGrid(facade).map((w) => Math.round(w.x * 1e4) / 1e4);
    for (const x of xs) expect(xs).toContain(-x);
  });

  it('has no windows when the facade asks for none', () => {
    expect(windowGrid({ ...facade, windowCols: 0, windowRows: 0 })).toEqual([]);
  });
});

describe('every venue is built like something', () => {
  it('gives every venue in the shared table a facade', () => {
    for (const venue of VENUE_ROWS) {
      expect(facadeFor(venue.id).storeys).toBeGreaterThanOrEqual(1);
    }
  });
});
