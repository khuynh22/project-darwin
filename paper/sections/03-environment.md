# The environment

`TODO(draft)` — ~500w, from the codebase. Cover:

- **Setup.** 3–10 agents, $10 start, goods economy (ore/food/tech) with per-agent
  specialties, progressive taxation, food consumption, elimination at balance ≤ 0.
- **Action space.** 20 actions in two tiers — 10 major (one per turn: work, trade, steal,
  invest, extort, sabotage, socialize…) plus 10 optional free actions (vouch, bluff, slander,
  gaslight, gift…), spanning cooperation, aggression, and explicit deception.
- **Information asymmetry.** Agents see their own exact balance but only fuzzy ranges for
  others (exact for allies/spouse); gaslight injects false events. This is what makes lying
  both possible and consequential.
- **★ The triple.** Every agent-turn logs private monologue + public broadcast + applied
  action and outcome — the core asset enabling intent-grounded labels.
- **Authority and reproducibility.** A server-side Oracle applies all mutations (parallel
  decide, sequential apply); environment RNG is seeded per (seed, turn). **LLM sampling is
  not deterministic** — report variance over seeds, never byte-identical reruns.
- **Conditions.** `neutral | honesty | deception` prompt suffixes, locked verbatim so
  cross-run comparisons stay valid.
- **Long horizon.** Up to 500 turns; our longest run reached **335 social turns**.

Include Figure 1 (schematic). `TODO(make)`
