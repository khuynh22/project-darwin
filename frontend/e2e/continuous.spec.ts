import { expect, test, type Page } from '@playwright/test';

/**
 * The gate on an event-shaped (v6) run.
 *
 * `triple.spec.ts` covers a turn-shaped run and must keep passing unchanged —
 * old releases do not get re-recorded. This covers the other clock: agents that
 * acted at unrelated moments, a transport measured in beats of simulation time
 * rather than in turns, and a walk whose duration the trace dictates.
 *
 * The Oracle is stubbed rather than started, for the same reason as the turn
 * gate: what is under test is the page.
 */

const RUN = 'clockfixture';

const AGENTS = [
  { agent_id: 'alpha', model: 'm/one', provider: 'openrouter', specialty: 'ore',
    turns_alive: 2, eliminated_at_turn: null, outcome: 'survived' },
  { agent_id: 'beta', model: 'm/two', provider: 'openrouter', specialty: 'tech',
    turns_alive: 2, eliminated_at_turn: null, outcome: 'survived' },
];

const state = (balance: number) => ({
  balance,
  trust_score: 50,
  inventory: {},
  alive: null,
  spouse_id: null,
});

/**
 * Deliberately ragged: alpha acts three times while beta acts once, and alpha's
 * second move is a 2-beat walk across town. A turn-shaped reader cannot express
 * any of that.
 */
const EVENTS = [
  {
    event_id: 1, tick: 0, agent_seq: 1, agent_id: 'alpha', wake_reason: 'start',
    action: 'rest', venue: 'lounge', monologue: 'ALPHA PRIVATE ONE',
    public_message: 'ALPHA PUBLIC ONE', outcome: 'ALPHA OUTCOME ONE',
    witnesses: [], travel_ticks: 0, deliberation_ticks: 0, busy_ticks: 0,
    wake_after: 1, wake_if: [], state: state(10),
  },
  {
    event_id: 2, tick: 0, agent_seq: 1, agent_id: 'beta', wake_reason: 'start',
    action: 'invest', venue: 'bank', monologue: 'BETA PRIVATE ONE',
    public_message: 'BETA PUBLIC ONE', outcome: 'BETA OUTCOME ONE',
    witnesses: [], travel_ticks: 0, deliberation_ticks: 0, busy_ticks: 500,
    wake_after: 20, wake_if: ['stolen_from'], state: state(8),
  },
  {
    event_id: 3, tick: 4000, agent_seq: 2, agent_id: 'alpha', wake_reason: 'scheduled',
    action: 'trade', venue: 'market', monologue: 'ALPHA PRIVATE TWO',
    public_message: 'ALPHA PUBLIC TWO', outcome: 'ALPHA OUTCOME TWO',
    witnesses: [], travel_ticks: 2000, deliberation_ticks: 0, busy_ticks: 3000,
    wake_after: 2, wake_if: [], state: state(11),
  },
  {
    event_id: 4, tick: 9000, agent_seq: 3, agent_id: 'alpha', wake_reason: 'scheduled',
    action: 'work', venue: 'work', monologue: 'ALPHA PRIVATE THREE',
    public_message: 'ALPHA PUBLIC THREE', outcome: 'ALPHA OUTCOME THREE',
    witnesses: [], travel_ticks: 1000, deliberation_ticks: 0, busy_ticks: 4000,
    wake_after: 3, wake_if: [], state: state(12),
  },
];

async function stubOracle(page: Page) {
  await page.route('**/releases/**', async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

    if (url.pathname.endsWith('/events')) {
      return json({ events: EVENTS, total: EVENTS.length, offset: 0, limit: 200 });
    }
    // A v6 run has no turns. The page must not fall back to an empty world.
    if (url.pathname.endsWith('/turns')) {
      return json({ turns: [], total: 0, offset: 0, limit: 200 });
    }
    if (url.pathname.endsWith('/verdicts')) return json({ verdicts: [] });
    if (url.pathname.endsWith('/scores')) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    }
    return json({
      run_id: RUN, condition: 'neutral', horizon: 12, n_agents: 2, n_turns: 0,
      state_fidelity: 'full', models: ['m/one', 'm/two'], has_verdicts: false,
      has_scores: false, about: '', agents: AGENTS,
    });
  });
}

async function toOverview(page: Page) {
  await page.getByRole('button', { name: 'overview' }).click();
}

test.beforeEach(async ({ page }) => {
  await stubOracle(page);
  await page.goto(`/gallery/${RUN}/3d`);
  await expect(page.locator('canvas')).toBeVisible();
});

test('an event-shaped run renders instead of falling back to an empty world', async ({
  page,
}) => {
  await expect(page.getByText('This browser cannot render the 3-D view')).toHaveCount(0);
  await toOverview(page);
  // A turn-shaped reader would find no turns here and show nothing at all.
  await expect(page.getByText('ALPHA PRIVATE ONE')).toBeVisible();
});

test('the transport is measured in beats, not turns', async ({ page }) => {
  // Agents no longer share a cadence, so "turn 40" names no single moment
  // while "beat 40" names exactly one.
  await expect(page.getByText(/beat \d/)).toBeVisible();
  await expect(page.getByText(/^turn \d/)).toHaveCount(0);
});

test('scrubbing forward advances simulation time', async ({ page }) => {
  const readout = page.getByText(/beat \d/);
  const before = await readout.textContent();

  await page.getByRole('button', { name: 'next' }).click();
  await page.getByRole('button', { name: 'next' }).click();

  expect(await readout.textContent()).not.toBe(before);
});

test('the triple stays legible on the new clock', async ({ page }) => {
  await toOverview(page);
  await expect(page.getByText('private reasoning')).toBeVisible();
  await expect(page.getByText('ALPHA PRIVATE ONE')).toBeVisible();
  await expect(page.getByText('public message')).toBeVisible();
  await expect(page.getByText('ALPHA PUBLIC ONE')).toBeVisible();
  await expect(page.getByText('applied action')).toBeVisible();
  await expect(page.getByText('ALPHA OUTCOME ONE')).toBeVisible();
});

test('an agent that slept keeps its last action rather than vanishing', async ({ page }) => {
  // beta acts once at tick 0 and then sleeps for the rest of the run. It is
  // still standing at the bank the whole time, and a frame that dropped it
  // would show a town emptying out as agents chose longer sleeps.
  await toOverview(page);
  for (let i = 0; i < 6; i += 1) {
    await page.getByRole('button', { name: 'next' }).click();
  }
  await expect(page.locator('canvas')).toBeVisible();
  await expect(page.getByText(/beat \d/)).toBeVisible();
});
