import { describe, expect, it } from 'vitest';
import { ACTIONS, STAGE_W, VENUES, VENUES_BY_ID, actionDef, venueForAction } from '@/lib/town';
import { BUILT_VENUE_ROWS, ECONOMY, UBIQUITOUS_ACTIONS } from '@/lib/worldData';

describe('actionDef', () => {
  it('resolves a known action', () => {
    expect(actionDef('work')?.venue).toBe('work');
  });

  it('invents a placeholder for an action the backend added and the table has not', () => {
    // The table must never be the reason a turn cannot be displayed: a backend
    // action with no entry still gets a venue, so the world stays renderable.
    const unknown = actionDef('teleport_sideways');
    expect(unknown).toBeDefined();
    expect(unknown?.intent).toBe('teleport sideways');
  });

  it('is undefined only for a missing id', () => {
    expect(actionDef(undefined)).toBeUndefined();
  });
});

describe('venueForAction', () => {
  it('maps every action in the table to a venue that exists', () => {
    for (const id of Object.keys(ACTIONS)) {
      if (UBIQUITOUS_ACTIONS.has(id)) continue;
      const venue = venueForAction(id);
      expect(venue, `action ${id} has no venue`).toBeDefined();
      expect(VENUES_BY_ID[venue!.id]).toBeDefined();
    }
  });

  // The invariant whose absence let the `anywhere` sentinel reach the renderer:
  // resolving an action to a venue may never yield an id outside the built set,
  // because everything downstream indexes maps keyed by exactly that set.
  it('never resolves anything to a venue outside the built set', () => {
    const built = new Set(BUILT_VENUE_ROWS.map((v) => v.id));
    const ids = [...Object.keys(ACTIONS), 'travel', 'teleport_sideways', ''];
    for (const id of ids) {
      const venue = venueForAction(id);
      if (venue === undefined) continue;
      expect(built.has(venue.id), `${id} -> ${venue.id}`).toBe(true);
    }
  });
});

describe('town reads the shared table', () => {
  it('renders exactly the built venues', () => {
    expect(VENUES.map((v) => v.id).sort()).toEqual(BUILT_VENUE_ROWS.map((v) => v.id).sort());
  });

  it('takes venue coordinates from the shared data', () => {
    for (const venue of VENUES) {
      const row = BUILT_VENUE_ROWS.find((v) => v.id === venue.id)!;
      expect(venue.x).toBe(row.x);
      expect(venue.y).toBe(row.y);
    }
  });

  it('takes the stage size from the shared data', () => {
    expect(STAGE_W).toBe(ECONOMY.stageW);
  });

  it('gives every venue a colour, styled or not', () => {
    for (const venue of VENUES) {
      expect(venue.body).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(venue.roof).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('carries the summary through to the action definition', () => {
    expect(ACTIONS.invest.summary).toContain('Tax-exempt');
  });
});
