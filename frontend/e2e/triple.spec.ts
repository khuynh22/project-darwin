import { expect, test, type Page } from '@playwright/test';

/**
 * The gate on the 3-D view's acceptance criterion.
 *
 * With the 2-D town gone there is no second place to read an agent's private
 * reasoning, public message, applied action and verdict. A world that renders
 * beautifully and buries the triple is a regression, not a feature (spec
 * 2026-08-24 §6), so this asserts the four fields are on screen.
 *
 * The Oracle is stubbed rather than started: what is under test is the page,
 * and the released trace it would otherwise read is gitignored, so CI has no
 * copy of it.
 */

const RUN = 'gatefixture';

const AGENTS = [
  { agent_id: 'alpha', model: 'm/one', provider: 'openrouter', specialty: 'ore',
    turns_alive: 2, eliminated_at_turn: null, outcome: 'survived' },
  { agent_id: 'beta', model: 'm/two', provider: 'openrouter', specialty: 'tech',
    turns_alive: 2, eliminated_at_turn: null, outcome: 'survived' },
];

const TURNS = [
  {
    turn: 1, agent_id: 'alpha', action: 'work',
    monologue: 'ALPHA PRIVATE ONE', public_message: 'ALPHA PUBLIC ONE',
    outcome: 'ALPHA OUTCOME ONE', arguments: {},
    state: { balance: 10, trust_score: 50, inventory: {}, alive: null, spouse_id: null },
    instrument: { tool_call_ok: true, note: '' },
  },
  {
    turn: 1, agent_id: 'beta', action: 'bet',
    monologue: 'BETA PRIVATE ONE', public_message: 'BETA PUBLIC ONE',
    outcome: 'BETA OUTCOME ONE', arguments: {},
    state: { balance: 8, trust_score: 40, inventory: {}, alive: null, spouse_id: null },
    instrument: { tool_call_ok: true, note: '' },
  },
  {
    turn: 2, agent_id: 'alpha', action: 'trade',
    monologue: 'ALPHA PRIVATE TWO', public_message: 'ALPHA PUBLIC TWO',
    outcome: 'ALPHA OUTCOME TWO', arguments: {},
    state: { balance: 11, trust_score: 51, inventory: {}, alive: null, spouse_id: null },
    instrument: { tool_call_ok: true, note: '' },
  },
  {
    turn: 2, agent_id: 'beta', action: 'steal',
    monologue: 'BETA PRIVATE TWO', public_message: 'BETA PUBLIC TWO',
    outcome: 'BETA OUTCOME TWO', arguments: {},
    state: { balance: 7, trust_score: 35, inventory: {}, alive: null, spouse_id: null },
    instrument: { tool_call_ok: true, note: '' },
  },
];

const VERDICTS = [
  {
    turn: 1, agent_id: 'alpha', is_deceptive: true, deception_type: 'misdirection',
    target_id: 'beta', confidence: 0.83, sophistication: 3,
    rationale: 'ALPHA RATIONALE ONE',
  },
];

async function stubOracle(page: Page) {
  await page.route('**/releases/**', async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

    if (url.pathname.endsWith('/turns')) {
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const limit = Number(url.searchParams.get('limit') ?? 50);
      return json({
        turns: TURNS.slice(offset, offset + limit),
        total: TURNS.length,
        offset,
        limit,
      });
    }
    if (url.pathname.endsWith('/verdicts')) return json({ verdicts: VERDICTS });
    if (url.pathname.endsWith('/scores')) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    }
    return json({
      run_id: RUN, condition: 'neutral', horizon: 2, n_agents: 2, n_turns: TURNS.length,
      state_fidelity: 'full', models: ['m/one', 'm/two'], has_verdicts: true,
      has_scores: false, about: '', agents: AGENTS,
    });
  });
}

test.beforeEach(async ({ page }) => {
  await stubOracle(page);
  await page.goto(`/gallery/${RUN}/3d`);
  await expect(page.locator('canvas')).toBeVisible();
});

test('the world renders rather than falling back to the no-WebGL notice', async ({ page }) => {
  await expect(page.getByText('This browser cannot render the 3-D view')).toHaveCount(0);
  const live = await page.evaluate(() => {
    const canvas = document.querySelector('canvas');
    const gl = canvas?.getContext('webgl2') ?? canvas?.getContext('webgl');
    return Boolean(gl) && !(gl as WebGLRenderingContext).isContextLost();
  });
  expect(live, 'the WebGL context must survive mounting').toBe(true);
});

test('all four fields of the triple are visible for the selected agent-turn', async ({ page }) => {
  await expect(page.getByText('private reasoning')).toBeVisible();
  await expect(page.getByText('ALPHA PRIVATE ONE')).toBeVisible();

  await expect(page.getByText('public message')).toBeVisible();
  await expect(page.getByText('ALPHA PUBLIC ONE')).toBeVisible();

  await expect(page.getByText('applied action')).toBeVisible();
  await expect(page.getByText('ALPHA OUTCOME ONE')).toBeVisible();

  await expect(page.getByText('judge')).toBeVisible();
  await expect(page.getByText('misdirection')).toBeVisible();
  await expect(page.getByText('conf 0.83')).toBeVisible();
  await expect(page.getByText('ALPHA RATIONALE ONE')).toBeVisible();
});

test('stepping to the next turn moves the panel with the world', async ({ page }) => {
  await expect(page.getByText('ALPHA PRIVATE ONE')).toBeVisible();

  await page.getByRole('button', { name: 'next' }).click();

  await expect(page.getByText('ALPHA PRIVATE TWO')).toBeVisible();
  await expect(page.getByText('ALPHA PRIVATE ONE')).toHaveCount(0);
  // Turn 2 has no verdict in the fixture, and the panel must say so rather
  // than leave a gap that reads as "not deceptive".
  await expect(page.getByText('No verdict')).toBeVisible();
});

test('an agent with no verdict still shows its triple', async ({ page }) => {
  await page.getByRole('button', { name: 'next' }).click();
  await expect(page.getByText('ALPHA OUTCOME TWO')).toBeVisible();
  await expect(page.getByText('ALPHA PUBLIC TWO')).toBeVisible();
});
