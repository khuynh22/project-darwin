# Ten-model, 335-turn leaderboard (2026-07-26)

Ten frozen frontier models share one open survival economy for 335 turns and are
told only to survive. Every agent-turn is recorded as the **triple** — the stated
private reasoning, the public broadcast, and the action the engine actually
applied — and judged offline for deception only when those channels contradict.

**Read the caveats.** This trace is `state_fidelity: partial`: the export carries
the triple but no per-turn balances, so probes mined from it have no pressure
tier. Kimi is present because it was a real agent and a legitimate deception
target, but it is excluded as a *deceiver* — 188 of its 333 turns (56%) were
tool-call fallbacks, visible here as `instrument.tool_call_ok: false`.

Deception rates are within-judge quantities. A second judge family labelled the
same turns at a different absolute rate, so treat the ordering, not the level, as
the signal — and see the paper's claim ledger before quoting either.
