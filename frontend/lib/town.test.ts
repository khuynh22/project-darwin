import { describe, expect, it } from 'vitest';
import { ACTIONS, VENUES_BY_ID, actionDef, venueForAction } from '@/lib/town';

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
      const venue = venueForAction(id);
      expect(venue, `action ${id} has no venue`).toBeDefined();
      expect(VENUES_BY_ID[venue!.id]).toBeDefined();
    }
  });
});
