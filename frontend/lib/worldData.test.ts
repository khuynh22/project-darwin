import { describe, expect, it } from 'vitest';
import {
  ACTION_ROWS,
  BUILT_VENUE_ROWS,
  ECONOMY,
  GOOD_PRICES,
  VENUE_ROWS,
  actionsAt,
} from '@/lib/worldData';

const DISTRICTS = new Set(['plaza', 'civic', 'industry', 'vice']);

describe('shared world data', () => {
  it('loads every venue with a well-formed row', () => {
    expect(VENUE_ROWS.length).toBeGreaterThan(0);
    for (const venue of VENUE_ROWS) {
      expect(typeof venue.id).toBe('string');
      expect(typeof venue.label).toBe('string');
      expect(DISTRICTS.has(venue.district)).toBe(true);
      expect(['built', 'planned']).toContain(venue.status);
      expect(Number.isFinite(venue.x)).toBe(true);
      expect(Number.isFinite(venue.y)).toBe(true);
    }
  });

  it('loads every action with a well-formed row', () => {
    for (const action of Object.values(ACTION_ROWS)) {
      expect(['major', 'free']).toContain(action.tier);
      expect(action.summary.length).toBeGreaterThan(10);
      expect(ACTION_ROWS[action.id].venue).toBeTruthy();
    }
  });

  it('places every action at a venue that exists and is built', () => {
    const built = new Set(BUILT_VENUE_ROWS.map((v) => v.id));
    for (const action of Object.values(ACTION_ROWS)) {
      expect(built.has(action.venue), `${action.id} -> ${action.venue}`).toBe(true);
    }
  });

  it('agrees with the venue action lists', () => {
    for (const venue of BUILT_VENUE_ROWS) {
      expect(actionsAt(venue.id).map((a) => a.id)).toEqual(venue.actions);
    }
  });

  it('carries a generated stage and walk speed', () => {
    expect(ECONOMY.stageW).toBeGreaterThan(0);
    expect(ECONOMY.walkUnitsPerBeat).toBeGreaterThan(0);
    expect(GOOD_PRICES.food).toBe(0.25);
  });
});
