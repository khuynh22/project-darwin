// Project Darwin — how the town looks.
//
// Identity, position and the action list come from shared/, which the Oracle
// reads too. What lives here is presentation: family tints, icons, intent
// verbs and the agent palette. The frontend is still a pure viewer.

import { ACTION_ROWS, BUILT_VENUE_ROWS, ECONOMY, type ActionRow } from '@/lib/worldData';

export type FamilyId =
  | 'economy'
  | 'prosocial'
  | 'aggression'
  | 'deception'
  | 'social'
  | 'movement';

export interface Family {
  id: FamilyId;
  label: string;
  color: string;
  soft: string;
  emoji: string;
}

export type VenueId = string;

export interface Venue {
  id: VenueId;
  label: string;
  sub: string;
  icon: string;
  x: number; // logical px in the generated stage
  y: number;
  body: string;
  roof: string;
  actions: string[];
}

export interface ActionDef {
  id: string;
  family: FamilyId;
  emoji: string;
  venue: VenueId;
  intent: string;
  summary: string;
}

export const STAGE_W = ECONOMY.stageW;
export const STAGE_H = ECONOMY.stageH;

export const FAMILIES: Record<FamilyId, Family> = {
  economy: { id: 'economy', label: 'economy', color: '#7DA7E1', soft: '#D9E5FF', emoji: '💰' },
  prosocial: { id: 'prosocial', label: 'prosocial', color: '#6FBF8E', soft: '#D7F0DF', emoji: '💚' },
  aggression: { id: 'aggression', label: 'aggression', color: '#E68A8A', soft: '#FFDADA', emoji: '😈' },
  deception: { id: 'deception', label: 'deception', color: '#E6B570', soft: '#FFE9C9', emoji: '🤥' },
  social: { id: 'social', label: 'social', color: '#B594D8', soft: '#EADDFF', emoji: '🤝' },
  movement: { id: 'movement', label: 'movement', color: '#9AA7B8', soft: '#E4E8EE', emoji: '🚶' },
};

type Cosmetics = { icon: string; body: string; roof: string };

const COSMETICS: Record<string, Cosmetics> = {
  plaza: { icon: '⛲', body: '#E8E4DA', roof: '#B9B2A4' },
  work: { icon: '🔨', body: '#FFE0B5', roof: '#E8A766' },
  market: { icon: '🏪', body: '#FFD1C2', roof: '#D87E66' },
  bank: { icon: '🏦', body: '#D9E5FF', roof: '#7AA0D4' },
  casino: { icon: '🎰', body: '#FFD9F0', roof: '#D88AB8' },
  lounge: { icon: '☕', body: '#E2DAFF', roof: '#9B7FCC' },
  alley: { icon: '🌙', body: '#D2D2D2', roof: '#7E7E7E' },
  registry: { icon: '🗂️', body: '#E6E9F0', roof: '#8C93A8' },
  courthouse: { icon: '⚖️', body: '#EFEAE0', roof: '#9A8F7A' },
  press: { icon: '📰', body: '#F2EFE6', roof: '#A9A08C' },
  tavern: { icon: '🍺', body: '#F0DCC0', roof: '#B98D5A' },
  farm: { icon: '🌾', body: '#E5F0C8', roof: '#8FAE5C' },
  mine: { icon: '⛏️', body: '#D8D2C8', roof: '#8A7F70' },
  workshop: { icon: '🛠️', body: '#FFE3C9', roof: '#C98B54' },
  warehouse: { icon: '📦', body: '#DCD9D2', roof: '#8E887C' },
  academy: { icon: '📚', body: '#DCE8F5', roof: '#7590B0' },
  guild_hall: { icon: '🛡️', body: '#E4DCEF', roof: '#8C7BA8' },
  pawnshop: { icon: '💍', body: '#F2E2CE', roof: '#B08A5E' },
  insurance: { icon: '☂️', body: '#DFEAEA', roof: '#7E9A9A' },
  estate: { icon: '🏘️', body: '#F0E0DC', roof: '#B07E76' },
  temple: { icon: '🕯️', body: '#F4EEE2', roof: '#A99270' },
};

// A venue nobody has styled yet must still render — the same tolerance
// actionDef gives an action the table has not caught up with.
const DEFAULT_COSMETICS: Cosmetics = { icon: '🏠', body: '#E4E4E4', roof: '#8E8E8E' };

function subtitle(actions: string[]): string {
  const verbs = actions.slice(0, 2).map((id) => ACTION_ROWS[id]?.intent ?? id);
  return verbs.join(' · ') || 'Public ground';
}

export const VENUES: Venue[] = BUILT_VENUE_ROWS.map((row) => ({
  id: row.id,
  label: row.label,
  sub: subtitle(row.actions),
  x: row.x,
  y: row.y,
  actions: row.actions,
  ...(COSMETICS[row.id] ?? DEFAULT_COSMETICS),
}));

export const VENUES_BY_ID: Record<string, Venue> = Object.fromEntries(VENUES.map((v) => [v.id, v]));

function toDef(row: ActionRow): ActionDef {
  const family = (row.family in FAMILIES ? row.family : 'social') as FamilyId;
  return {
    id: row.id,
    family,
    emoji: row.emoji,
    venue: row.venue,
    intent: row.intent,
    summary: row.summary,
  };
}

export const ACTIONS: Record<string, ActionDef> = Object.fromEntries(
  Object.values(ACTION_ROWS).map((row) => [row.id, toDef(row)]),
);

// Where a freshly-loaded agent stands before it has picked an action.
export const HOME_VENUES: VenueId[] = VENUES.map((v) => v.id);

export const COLOR_HEX: Record<string, string> = {
  red: '#F4A6A0',
  blue: '#A8D3F5',
  green: '#B5E8C9',
  purple: '#CFC4F2',
  orange: '#FFCBA0',
  cyan: '#A8E6E0',
  pink: '#FFC2DA',
  yellow: '#FFE6A8',
  teal: '#A8DDD0',
  indigo: '#BAB4F0',
};

// Shown for any action the backend has but this map does not yet. Later layers
// keep adding actions, and an unmapped one should read as unknown rather than
// silently vanish from the town and the log.
const UNKNOWN_ACTION: ActionDef = {
  id: 'unknown',
  family: 'social',
  emoji: '❓',
  venue: 'plaza',
  intent: 'do something new',
  summary: 'An action the town has not been told about yet.',
};

export function actionDef(id: string | undefined): ActionDef | undefined {
  if (!id) return undefined;
  return ACTIONS[id] ?? { ...UNKNOWN_ACTION, id, intent: id.replace(/_/g, ' ') };
}

export function familyOf(actionId: string | undefined): Family | undefined {
  const a = actionDef(actionId);
  return a ? FAMILIES[a.family] : undefined;
}

export function venueForAction(actionId: string | undefined): Venue | undefined {
  const a = actionDef(actionId);
  return a ? VENUES_BY_ID[a.venue] : undefined;
}

// Slot positions around each venue so multiple critters share without overlap.
// Mirrors the design's wider horizontal spacing so name tags don't collide.
const SLOTS = [
  { dx: -72, dy: 76 },
  { dx: 0, dy: 82 },
  { dx: 72, dy: 76 },
  { dx: -40, dy: 130 },
  { dx: 40, dy: 130 },
  { dx: -100, dy: 100 },
  { dx: 100, dy: 100 },
  { dx: 0, dy: 150 },
  { dx: -60, dy: 50 },
  { dx: 60, dy: 50 },
];

export function venueSlot(venue: Venue, slotIdx: number): { x: number; y: number } {
  const s = SLOTS[slotIdx % SLOTS.length];
  return { x: venue.x + s.dx, y: venue.y + s.dy };
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

export function fmtTime(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
