import { VENUE_FOOTPRINT } from '@/lib/world3d';

/**
 * What each venue is built like.
 *
 * Six identical sheds is not a town you can navigate, so each venue gets a
 * shape you can recognise from across the plaza — a two-storey bank, a low
 * shuttered alley, a workshop with an awning.
 *
 * The hard constraint is that the walker collides with a box of
 * VENUE_FOOTPRINT and nothing else. Eaves that overhang past it are eaves you
 * walk straight through, so every dimension here is measured against it.
 */

/** Wall-to-wall, leaving room for the roof to overhang inside the footprint. */
export const WALL = 4.35;

/** How far the roof reaches past the wall on each side. */
export const EAVES = 0.36;

export const STOREY = 2.4;

export const DOOR = { width: 1.05, height: 1.95 } as const;

const WINDOW = { width: 0.62, height: 0.78 } as const;

export type Roof = 'gable' | 'hip' | 'flat';

export type Facade = {
  storeys: number;
  windowCols: number;
  windowRows: number;
  roof: Roof;
  /** A canopy over the door — a shopfront rather than a shed. */
  awning: boolean;
  chimney: boolean;
  /** Pillars either side of the door, for the places that want to look solemn. */
  columns: boolean;
};

const DEFAULT_FACADE: Facade = {
  storeys: 1,
  windowCols: 2,
  windowRows: 1,
  roof: 'gable',
  awning: false,
  chimney: false,
  columns: false,
};

const BY_VENUE: Record<string, Facade> = {
  work: { storeys: 1, windowCols: 4, windowRows: 1, roof: 'gable', awning: true, chimney: true, columns: false },
  market: { storeys: 1, windowCols: 2, windowRows: 1, roof: 'hip', awning: true, chimney: false, columns: false },
  bank: { storeys: 2, windowCols: 4, windowRows: 2, roof: 'flat', awning: false, chimney: false, columns: true },
  casino: { storeys: 2, windowCols: 2, windowRows: 2, roof: 'hip', awning: true, chimney: false, columns: false },
  lounge: { storeys: 1, windowCols: 2, windowRows: 1, roof: 'gable', awning: false, chimney: true, columns: false },
  alley: { storeys: 1, windowCols: 0, windowRows: 0, roof: 'flat', awning: false, chimney: false, columns: false },
  plaza: { storeys: 1, windowCols: 0, windowRows: 0, roof: 'flat', awning: false, chimney: false, columns: true },
  registry: { storeys: 2, windowCols: 3, windowRows: 2, roof: 'flat', awning: false, chimney: false, columns: true },
  courthouse: { storeys: 2, windowCols: 2, windowRows: 2, roof: 'gable', awning: false, chimney: false, columns: true },
  press: { storeys: 1, windowCols: 3, windowRows: 1, roof: 'gable', awning: true, chimney: true, columns: false },
  tavern: { storeys: 2, windowCols: 2, windowRows: 2, roof: 'gable', awning: true, chimney: true, columns: false },
  farm: { storeys: 1, windowCols: 2, windowRows: 1, roof: 'gable', awning: true, chimney: false, columns: false },
  mine: { storeys: 1, windowCols: 0, windowRows: 0, roof: 'gable', awning: false, chimney: true, columns: false },
  workshop: { storeys: 1, windowCols: 4, windowRows: 1, roof: 'gable', awning: true, chimney: true, columns: false },
  warehouse: { storeys: 1, windowCols: 1, windowRows: 1, roof: 'flat', awning: false, chimney: false, columns: false },
  academy: { storeys: 2, windowCols: 4, windowRows: 2, roof: 'hip', awning: false, chimney: true, columns: true },
  guild_hall: { storeys: 2, windowCols: 3, windowRows: 2, roof: 'gable', awning: false, chimney: true, columns: true },
  pawnshop: { storeys: 1, windowCols: 2, windowRows: 1, roof: 'flat', awning: true, chimney: false, columns: false },
  insurance: { storeys: 2, windowCols: 3, windowRows: 2, roof: 'flat', awning: false, chimney: false, columns: false },
  estate: { storeys: 2, windowCols: 2, windowRows: 2, roof: 'hip', awning: true, chimney: true, columns: false },
  temple: { storeys: 1, windowCols: 2, windowRows: 1, roof: 'hip', awning: false, chimney: false, columns: true },
};

export function facadeFor(venueId: string): Facade {
  return BY_VENUE[venueId] ?? DEFAULT_FACADE;
}

export type Extent = {
  width: number;
  depth: number;
  /** Ground to the top of the walls. */
  wallHeight: number;
  /** Ground to the ridge, chimney excluded. */
  height: number;
};

const ROOF_RISE: Record<Roof, number> = { gable: 1.15, hip: 1.0, flat: 0.28 };

export function facadeExtent(facade: Facade): Extent {
  const wallHeight = STOREY * facade.storeys;
  const spread = Math.min(WALL + EAVES * 2, VENUE_FOOTPRINT);
  return {
    width: spread,
    depth: spread,
    wallHeight,
    height: wallHeight + ROOF_RISE[facade.roof],
  };
}

/**
 * Cone radius for a four-sided pyramid whose square base spans `width`.
 *
 * `coneGeometry(r, h, 4)` puts its base vertices at distance `r` on the axes —
 * a diamond. Turned 45 degrees to line up with the walls, that square spans
 * `r * sqrt(2)`, so sizing the radius by eye overhangs the footprint.
 */
export function hipConeRadius(width: number): number {
  return width / Math.SQRT2;
}

export type Window = { x: number; y: number; width: number; height: number };

/**
 * Windows across the front, skipping the doorway.
 *
 * Laid out in pairs outward from the centre so the result is symmetric about
 * the door however many columns are asked for, and so an odd column never
 * lands on the doorway itself.
 */
export function windowGrid(facade: Facade): Window[] {
  const { windowCols, windowRows } = facade;
  if (windowCols <= 0 || windowRows <= 0) return [];

  const wallHeight = STOREY * facade.storeys;
  const pairs = Math.ceil(windowCols / 2);
  const edge = WALL / 2 - WINDOW.width / 2 - 0.28;
  const inner = DOOR.width / 2 + WINDOW.width / 2 + 0.22;
  const span = Math.max(0, edge - inner);

  const out: Window[] = [];
  for (let row = 0; row < windowRows; row++) {
    // Ground-floor windows clear the door head; upper floors sit in their storey.
    const base = row === 0 ? DOOR.height + 0.3 : STOREY * row + 0.62;
    const y = Math.min(base + WINDOW.height / 2, wallHeight - WINDOW.height / 2 - 0.2);

    for (let pair = 0; pair < pairs; pair++) {
      const t = pairs === 1 ? 0 : pair / (pairs - 1);
      const x = inner + span * t;
      out.push({ x, y, ...WINDOW });
      if (out.length < windowCols * (row + 1)) out.push({ x: -x, y, ...WINDOW });
    }
  }
  return out.slice(0, windowCols * windowRows);
}
