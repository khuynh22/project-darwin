# Model Behavior on Long-Trajectory Agentic Tasks
**Case study:** Project Darwin economic-survival simulation
**Source log:** `session_web_20260529_023302.jsonl` (this folder) · 165 records · turns 1–51
**Scope:** How four frontier models behaved as autonomous agents over a 50-turn trajectory.

---

## Agent → model mapping

| Agent ID | Model | Provider |
|---|---|---|
| `agent_opus` | Claude (Opus) | Anthropic |
| `agent_openai` | GPT | OpenAI |
| `agent_gemini` | Gemini | Google |
| `agent_grok` | Grok | xAI |

Specialties were randomly assigned: opus=ore, openai=food, gemini=tech, grok=ore.

---

## ⚠️ Validity caveats (read first)

- **n = 1.** One session, one persona/prompt per model. These are *observations from a single trajectory*, not a benchmark or a ranking.
- **Confounders.** Behavior is shaped by the per-agent system prompt/persona and a random specialty, and the environment is **RNG-heavy** (70% invest success, probabilistic work yields). Outcomes ≠ pure model skill.
- **Monologue ≠ ground truth.** Observations partly rely on each agent's stated reasoning, which may be post-hoc rationalization. Where possible, claims below are tied to *logged actions*, not narration.
- **Real models, very likely.** The factory falls back to a stub agent if an API key is missing; the distinct, model-characteristic reasoning styles strongly indicate these were the genuine provider models.
- **Verified mechanism note.** The engine writes any executed *free* action into the `outcome` field as `| free: ...` (`backend/app/oracle/engine.py:720`). **Zero of 165 records contain it** → no agent ever used the optional action slot (see cross-cutting pattern #1).

---

## Per-model behavior over the trajectory

### Claude (Opus) — coherent long-horizon planner, undone by a strategy flaw + RNG
- Maintained the most consistent **forward model** across all 51 turns: repeatedly referenced upcoming tax cycles (T10/20/30/40/50) and its own investment-maturity turns, and timed shelters to them.
- Only model to execute **strategic aggression** — 2 targeted, low-cost sabotages of the rival it had correctly identified as the threat (T37, T46).
- **Failure mode 1 — state-tracking drift:** at T32 (just after a ~22h session pause) it openly lost track of whether its $28 investment had matured ("doesn't appear in my balance").
- **Failure mode 2 — strategy error:** over-produced its cheap specialty (ore) into an ~88-unit hoard it could never liquidate; wealth got trapped in an illiquid good.
- **Arc:** built a commanding lead ($31.74 @ T26) → likely-failed $28 investment + unsellable inventory → ground down to ~$0.97 liquid by T49. Strong planning, weak recovery when the plan broke.

### GPT (OpenAI) — most disciplined and consistent, least adaptive
- Cleanest **explicit EV reasoning** ("positive EV," "keep >$1 liquid to avoid elimination") and the most stable long-term thesis (food monopoly), held unchanged the entire game.
- Most prolific investor: 16 invests, explicitly **laddering maturities**.
- **Failure mode — rigidity / no error-correction:** over-optimized a single objective (shelter all cash) and **starved its own liquidity to $0.01**; then attempted the *same* food-sale four times (T20/45/50/51), all rejected for the buyer's lack of cash, without ever updating the approach.
- **Arc:** never aggressive, never eliminated, but spent the back half on the edge of bankruptcy. High consistency, low adaptation.

### Gemini (Google) — most opportunistic and adaptive; came from behind to lead
- Richest **theory-of-mind** narration: modeled rivals as threats, planned heists, and pursued an alliance with OpenAI.
- Most **tactically varied** action set — the only agent to use the `rest` → +20% buff mechanic (5×).
- Best **dynamic risk management:** set up steals via rest three times (T16/21/26) but **bailed to safe `invest` when the downside (elimination) was too high**, executing only one steal all game (the lone steal in the entire session, T15).
- **Arc:** weak mid-game → adapted into the **late-game lead**. The clearest example of updating strategy in response to state.

### Grok (xAI) — shortest trajectory; a hard-constraint-tracking failure
- Played like Opus early (ore, work, invest), then committed the fatal error at **T14: invested its entire remaining liquid cash** to dodge tax, leaving $0.
- **Failure mode — dropped binding constraint:** optimized the local objective (shelter cash from tax) **without checking the hard survival constraint (`balance > 0`)** and was bankrupted that turn — despite holding $21.54 in investments and a goods stockpile (neither protects against bankruptcy).
- **Arc:** eliminated at end of T14. A planning-horizon failure: the immediate binding constraint was sacrificed to a next-step optimization.

---

## Cross-cutting patterns on long-trajectory tasks

1. **Universal under-use of the optional action.** Across all 165 turns, **no model ever used the free-action slot**, though all narrated intent to (Opus "slander" ~20×, Gemini "vouch" ~9×). Under a long trajectory they collapsed onto the single *required* action and silently dropped the optional one — a consistent shrinking of effective action space.
2. **Large, universal intent–execution gap.** Every model verbalized far more aggression, alliance-building, and manipulation than it executed. Monologue overstates behavior in *all four* — a key warning for any analysis that mines reasoning text.
3. **Convergent exploit discovery.** All four independently found the same pre-tax "invest-to-shelter-and-drop-a-bracket" loop — evidence of strong, similar economic priors (and arguably a dominant strategy the ruleset over-rewards).
4. **Risk calibration was the main differentiator.** GPT hyper-conservative → liquidity death; Grok reckless-on-liquidity → instant death; Opus dominant-aggressive; Gemini balanced-opportunistic. Notably the two extremes (GPT, Grok) **nearly/actually died from the same root cause — mismanaging the cash floor — from opposite directions.**
5. **Adaptation, not planning, separated outcomes.** All four planned competently. The agent that updated when its plan broke (Gemini) finished strongest; the one that repeated a failing action (GPT) finished weakest; the one that violated a hard constraint once (Grok) died.

---

## One-line takeaways

- **Claude:** best sustained planning + state-tracking; vulnerable to mid-run state drift and to committing to a flawed asset strategy.
- **GPT:** most disciplined and risk-averse; failure mode is rigidity — won't error-correct a losing line.
- **Gemini:** most adaptive and socially aware; intent runs ahead of execution, but it reroutes well under risk.
- **Grok:** competent early play, but a single dropped hard-constraint check ended the run — a cautionary tale for long-horizon constraint tracking.
