import { describe, expect, it } from 'vitest';
import { FOCUS_RADIUS, focusTarget, focusVenue } from '@/lib/proximity';
import { VENUES } from '@/lib/town';
import { venuePosition, type Vec3 } from '@/lib/world3d';

const EYE: Vec3 = [0, 1.7, 0];
const NORTH: Vec3 = [0, 0, -1]; // three.js rest facing

const at = (agentId: string, x: number, z: number) => ({
  agentId,
  position: [x, 0, z] as Vec3,
});

describe('focusTarget', () => {
  it('picks whoever you are standing closest to, ahead of you', () => {
    const who = focusTarget(EYE, NORTH, [at('far', 0, -8), at('near', 1, -3)], null);
    expect(who).toBe('near');
  });

  it('prefers who you are looking at over who you are nearest', () => {
    // Walking into a crowd and reading whoever happens to be closest means the
    // panel describes a body that is not the one filling your screen.
    const who = focusTarget(
      EYE,
      NORTH,
      [at('centred', 0, -6), at('off-axis', 3.5, -1.5)],
      null,
    );
    expect(who).toBe('centred');
  });

  it('ignores someone behind you, however close', () => {
    // You cannot see them, so reading their monologue would be a lie about
    // what you are looking at.
    expect(focusTarget(EYE, NORTH, [at('behind', 0, 2)], null)).toBeNull();
  });

  it('ignores someone across the plaza', () => {
    expect(focusTarget(EYE, NORTH, [at('yonder', 0, -(FOCUS_RADIUS + 5))], null)).toBeNull();
  });

  it('is nobody when the town is empty', () => {
    expect(focusTarget(EYE, NORTH, [], null)).toBeNull();
  });

  it('keeps hold of who you were looking at rather than flickering', () => {
    // Two agents at nearly the same distance would otherwise swap every frame
    // as you breathe, and the panel would strobe between them.
    const agents = [at('a', -0.4, -4), at('b', 0.4, -4.02)];
    const first = focusTarget(EYE, NORTH, agents, null);
    expect(first).toBe('a');
    expect(focusTarget(EYE, NORTH, agents, 'b')).toBe('b');
  });

  it('lets go once you walk away from them', () => {
    const agents = [at('gone', 0, -(FOCUS_RADIUS * 2))];
    expect(focusTarget(EYE, NORTH, agents, 'gone')).toBeNull();
  });

  it('lets go once you turn your back on them', () => {
    expect(focusTarget(EYE, NORTH, [at('behind', 0, 3)], 'behind')).toBeNull();
  });

  it('breaks a dead tie the same way every time', () => {
    const agents = [at('b', 1, -4), at('a', -1, -4)];
    expect(focusTarget(EYE, NORTH, agents, null)).toBe(
      focusTarget(EYE, NORTH, [...agents].reverse(), null),
    );
  });
});

describe('focusVenue', () => {
  it('reports the building you are standing in front of', () => {
    const market = VENUES.find((v) => v.id === 'market')!;
    const [x, , z] = venuePosition(market);
    // Stand a few metres to the south, looking north at it.
    const eye: Vec3 = [x, 1.7, z + 6];
    const look: Vec3 = [0, 0, -1];

    expect(focusVenue(eye, look, VENUES, null)).toBe('market');
  });

  it('reports nothing when you are looking at the sky in an empty field', () => {
    const eye: Vec3 = [0, 1.7, 0];
    const look: Vec3 = [0, 1, 0];

    expect(focusVenue(eye, look, VENUES, null)).toBeNull();
  });
});
