import { ORACLE_HTTP } from "@/lib/ws";

export type StateFidelity = "full" | "partial";

export type ReleaseSummary = {
  run_id: string;
  condition: string;
  horizon: number;
  n_agents: number;
  n_turns: number;
  state_fidelity: StateFidelity;
  models: string[];
  has_verdicts: boolean;
  has_scores: boolean;
  about: string;
};

export type ReleaseAgent = {
  agent_id: string;
  model: string;
  provider: string;
  specialty: string;
  turns_alive: number;
  eliminated_at_turn: number | null;
  outcome: string;
};

export type ReleaseDetail = ReleaseSummary & { agents: ReleaseAgent[] };

export type TurnState = {
  balance: number | null;
  trust_score: number | null;
  inventory: Record<string, number> | null;
  alive: string[] | null;
  spouse_id: string | null;
};

export type ReleaseTurn = {
  turn: number;
  agent_id: string;
  monologue: string;
  public_message: string;
  action: string;
  arguments: Record<string, unknown>;
  outcome: string;
  state: TurnState;
  instrument: { tool_call_ok: boolean; note: string };
};

export type Verdict = {
  turn: number;
  agent_id: string;
  is_deceptive: boolean;
  deception_type: string;
  target_id: string | null;
  confidence: number;
  sophistication: number | null;
  rationale?: string;
  channels_in_conflict?: string[];
};

export type Rate = {
  successes: number;
  n: number;
  rate: number;
  low: number;
  high: number;
};

export type ModelScore = {
  model: string;
  propensity_overall: Rate;
  propensity_by_tier: Record<string, Rate>;
  susceptibility: Rate;
  sophistication_mean: number | null;
  sophistication_hist: Record<string, number>;
  pressure_threshold: number | null;
  excluded: number;
  untiered: number;
  divergence_mean: number;
  divergence_max: number;
};

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${ORACLE_HTTP}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export async function fetchReleases(): Promise<ReleaseSummary[]> {
  const data = await getJson<{ releases: ReleaseSummary[] }>("/releases");
  return data.releases;
}

export function fetchRelease(runId: string): Promise<ReleaseDetail> {
  return getJson<ReleaseDetail>(`/releases/${encodeURIComponent(runId)}`);
}

export async function fetchTurns(
  runId: string,
  offset: number,
  limit: number,
): Promise<{ turns: ReleaseTurn[]; total: number; offset: number; limit: number }> {
  return getJson(
    `/releases/${encodeURIComponent(runId)}/turns?offset=${offset}&limit=${limit}`,
  );
}

export async function fetchVerdicts(runId: string): Promise<Verdict[]> {
  const data = await getJson<{ verdicts: Verdict[] }>(
    `/releases/${encodeURIComponent(runId)}/verdicts`,
  );
  return data.verdicts;
}

export async function fetchScores(runId: string): Promise<ModelScore[]> {
  try {
    const data = await getJson<{ scores: ModelScore[] }>(
      `/releases/${encodeURIComponent(runId)}/scores`,
    );
    return data.scores;
  } catch {
    return [];
  }
}

export function verdictKey(turn: number, agentId: string): string {
  return `${turn}:${agentId}`;
}

export function indexVerdicts(verdicts: Verdict[]): Map<string, Verdict> {
  return new Map(verdicts.map((v) => [verdictKey(v.turn, v.agent_id), v]));
}
