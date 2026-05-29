export type AgentSnap = {
  agent_id: string;
  display_name: string;
  provider: string;
  balance: number;
  alive: boolean;
  spouse: string | null;
  allies: string[];
  enemies: string[];
  sprite: string;
  consecutive_errors: number;
  last_error: string | null;
  trust_score: number;
  steal_count: number;
  inventory: Record<string, number>;
  specialty: string;
  invested: number;
  rest_bonus: boolean;
  will_target: string | null;
};

export type ThoughtSnap = {
  turn: number;
  agent_id: string;
  monologue: string;
  public_message: string;
  action: string;
  arguments: Record<string, unknown>;
  outcome: string;
};

export type BalanceVisibility = "public" | "fuzzy" | "hidden";

export type WorldSnapshot = {
  turn: number;
  agents: AgentSnap[];
  recent_thoughts: ThoughtSnap[];
  balance_visibility?: BalanceVisibility;
};

export type PausedEvent = {
  event: "simulation_paused";
  turn: number;
  agent_id: string;
  reason: string;
  snapshot: WorldSnapshot;
};

export function connectOracle(
  onSnapshot: (snap: WorldSnapshot) => void,
  onPaused?: (evt: PausedEvent) => void,
): () => void {
  const httpBase =
    process.env.NEXT_PUBLIC_ORACLE_HTTP || "http://localhost:8000";
  const wsUrl = process.env.NEXT_PUBLIC_ORACLE_WS || "ws://localhost:8000/ws";

  fetch(`${httpBase}/state`)
    .then((r) => r.json())
    .then((snap: WorldSnapshot) => onSnapshot(snap))
    .catch(() => {});

  let ws: WebSocket | null = null;
  let closed = false;

  const open = () => {
    if (closed) return;
    ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.event === "simulation_paused" && onPaused) {
          onPaused(msg as PausedEvent);
        }
        if (msg.snapshot) onSnapshot(msg.snapshot as WorldSnapshot);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onerror = () => {};
    ws.onclose = () => {
      if (!closed) setTimeout(open, 1500);
    };
  };
  open();

  return () => {
    closed = true;
    ws?.close();
  };
}
