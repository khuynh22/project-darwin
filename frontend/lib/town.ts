// Project Darwin — town & action design data.
//
// Mirrors the cozy-tiny-town design handoff (venue ring around a central
// plaza), and maps the backend's 20 action ids onto venues + intent labels +
// family color tints. The frontend is still a pure viewer; this file only
// shapes how the snapshot is rendered.

export type FamilyId = 'economy' | 'prosocial' | 'aggression' | 'deception' | 'social';

export interface Family {
  id: FamilyId;
  label: string;
  color: string;
  soft: string;
  emoji: string;
}

export interface Venue {
  id: VenueId;
  label: string;
  sub: string;
  icon: string;
  x: number; // logical px in 780×560 stage
  y: number;
  body: string;
  roof: string;
}

export type VenueId =
  | 'work'
  | 'market'
  | 'bank'
  | 'casino'
  | 'lounge'
  | 'alley';

export interface ActionDef {
  id: string;
  family: FamilyId;
  emoji: string;
  venue: VenueId;
  intent: string;
}

// Stage logical size — matches the design's 780×560 town layer.
export const STAGE_W = 780;
export const STAGE_H = 560;

export const FAMILIES: Record<FamilyId, Family> = {
  economy: { id: 'economy', label: 'economy', color: '#7DA7E1', soft: '#D9E5FF', emoji: '💰' },
  prosocial: { id: 'prosocial', label: 'prosocial', color: '#6FBF8E', soft: '#D7F0DF', emoji: '💚' },
  aggression: { id: 'aggression', label: 'aggression', color: '#E68A8A', soft: '#FFDADA', emoji: '😈' },
  deception: { id: 'deception', label: 'deception', color: '#E6B570', soft: '#FFE9C9', emoji: '🤥' },
  social: { id: 'social', label: 'social', color: '#B594D8', soft: '#EADDFF', emoji: '🤝' },
};

export const VENUES: Venue[] = [
  { id: 'work', label: 'Work', sub: 'Labor', icon: '🔨', x: 390, y: 72, body: '#FFE0B5', roof: '#E8A766' },
  { id: 'market', label: 'Market', sub: 'Trade · Gift', icon: '🏪', x: 660, y: 180, body: '#FFD1C2', roof: '#D87E66' },
  { id: 'bank', label: 'Bank', sub: 'Invest', icon: '🏦', x: 660, y: 320, body: '#D9E5FF', roof: '#7AA0D4' },
  { id: 'casino', label: 'Casino', sub: 'Bet', icon: '🎰', x: 390, y: 416, body: '#FFD9F0', roof: '#D88AB8' },
  { id: 'lounge', label: 'Lounge', sub: 'Socialize', icon: '☕', x: 120, y: 320, body: '#E2DAFF', roof: '#9B7FCC' },
  { id: 'alley', label: 'Alley', sub: 'Shady deeds', icon: '🌙', x: 120, y: 180, body: '#D2D2D2', roof: '#7E7E7E' },
];

export const VENUES_BY_ID: Record<string, Venue> = Object.fromEntries(VENUES.map((v) => [v.id, v]));

// Every backend action id mapped to its venue + family + intent label.
export const ACTIONS: Record<string, ActionDef> = {
  // economy
  work: { id: 'work', family: 'economy', emoji: '🔨', venue: 'work', intent: 'to work' },
  trade: { id: 'trade', family: 'economy', emoji: '🔄', venue: 'market', intent: 'trade!' },
  invest: { id: 'invest', family: 'economy', emoji: '📈', venue: 'bank', intent: 'invest' },
  bet: { id: 'bet', family: 'economy', emoji: '🎲', venue: 'casino', intent: 'place a bet' },
  // prosocial
  charity: { id: 'charity', family: 'prosocial', emoji: '🎁', venue: 'market', intent: 'donate' },
  gift: { id: 'gift', family: 'prosocial', emoji: '💝', venue: 'market', intent: 'give a gift' },
  vouch: { id: 'vouch', family: 'prosocial', emoji: '🤲', venue: 'lounge', intent: 'vouch' },
  lend: { id: 'lend', family: 'prosocial', emoji: '💵', venue: 'bank', intent: 'lend coins' },
  will: { id: 'will', family: 'prosocial', emoji: '📜', venue: 'bank', intent: 'write a will' },
  // aggression
  steal: { id: 'steal', family: 'aggression', emoji: '🦝', venue: 'alley', intent: 'swipe!' },
  sabotage: { id: 'sabotage', family: 'aggression', emoji: '💣', venue: 'alley', intent: 'sabotage' },
  extort: { id: 'extort', family: 'aggression', emoji: '🪝', venue: 'alley', intent: 'shake down' },
  strike: { id: 'strike', family: 'aggression', emoji: '✊', venue: 'work', intent: 'strike!' },
  // deception
  slander: { id: 'slander', family: 'deception', emoji: '📣', venue: 'lounge', intent: 'spread rumors' },
  gaslight: { id: 'gaslight', family: 'deception', emoji: '🌀', venue: 'lounge', intent: 'gaslight' },
  bluff: { id: 'bluff', family: 'deception', emoji: '🎭', venue: 'casino', intent: 'bluff big' },
  // social
  socialize: { id: 'socialize', family: 'social', emoji: '💬', venue: 'lounge', intent: 'chitchat' },
  propose_deal: { id: 'propose_deal', family: 'social', emoji: '🤝', venue: 'lounge', intent: 'make a deal' },
  bribe: { id: 'bribe', family: 'social', emoji: '💼', venue: 'market', intent: 'bribe' },
  rest: { id: 'rest', family: 'social', emoji: '😴', venue: 'lounge', intent: 'take a rest' },
};

// Default home venue per agent color, so freshly-loaded agents
// have somewhere to stand before they pick an action.
export const HOME_VENUES: VenueId[] = ['work', 'market', 'bank', 'casino', 'lounge', 'alley'];

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

export function actionDef(id: string | undefined): ActionDef | undefined {
  if (!id) return undefined;
  return ACTIONS[id];
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
