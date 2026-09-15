// The shared world tables. Same files the Oracle loads, so the sign on a
// building and the prompt the agent received cannot disagree.
import actionsJson from '@shared/actions.json';
import economyJson from '@shared/economy.json';
import goodsJson from '@shared/goods.json';
import venuesJson from '@shared/venues.json';

export type District = 'plaza' | 'civic' | 'industry' | 'vice';
export type Tier = 'major' | 'free';

export interface ActionRow {
  id: string;
  tier: Tier;
  family: string;
  venue: string;
  beats: number;
  emoji: string;
  intent: string;
  summary: string;
}

export interface VenueRow {
  id: string;
  label: string;
  district: District;
  status: 'built' | 'planned';
  x: number;
  y: number;
  actions: string[];
}

export const VENUE_ROWS = venuesJson as VenueRow[];
export const BUILT_VENUE_ROWS = VENUE_ROWS.filter((v) => v.status === 'built');

export const ACTION_ROWS: Record<string, ActionRow> = Object.fromEntries(
  (actionsJson as ActionRow[]).map((a) => [a.id, a]),
);

export const GOOD_PRICES: Record<string, number> = Object.fromEntries(
  (goodsJson as { id: string; base_price: number }[]).map((g) => [g.id, g.base_price]),
);

export const ECONOMY = {
  taxCycleBeats: economyJson.tax_cycle_beats,
  walkUnitsPerBeat: economyJson.walk_units_per_beat,
  stageW: economyJson.stage_w,
  stageH: economyJson.stage_h,
};

export function actionsAt(venueId: string): ActionRow[] {
  const venue = VENUE_ROWS.find((v) => v.id === venueId);
  return venue ? venue.actions.map((id) => ACTION_ROWS[id]) : [];
}
