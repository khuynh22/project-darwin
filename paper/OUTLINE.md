# Outline

**Target venue (first):** Cooperative-AI / AI-safety workshop (flag-planting, ~4–8pp).
**Then:** NeurIPS Datasets & Benchmarks ("Evaluations & Datasets" track) or AIES (full length).

**Working title:** *Measuring Sustained, Intent-Grounded Deception Among Competing
Frontier Models in an Open Survival Economy*

**One-sentence thesis:** Frontier LLMs under competitive survival pressure spontaneously
deceive each other; the propensity is model-specific, sustained over long horizons, and
not obviously adaptive — measurable because we log private reasoning, public speech, and
action for every turn.

| § | File | Target | Content | Gate |
|---|---|---|---|---|
| — | `00-abstract.md` | 150–200w | Write **last**. | after §5 |
| 1 | `01-introduction.md` | 600–800w | Deployment is multi-agent + long-horizon; deception eval is single-agent + one-shot. Contributions: instrument, intent-grounded metric, coherence metric, first findings. | ready |
| 2 | `02-related-work.md` | 500–700w | The 6 comparators + where each stops. Own the *integration*, not any axis. | ready |
| 3 | `03-environment.md` | 500w | Darwin: 3–10 agents, 20 actions, survival economy, info asymmetry, seeds, conditions. | ready |
| 4 | `04-method.md` | 700–900w | The triple; judge + taxonomy + v2 prompt; conditions; metrics (rate, episodes, coherence); reliability plan. | ready (coherence formula TODO) |
| 5 | `05-results.md` | 800–1000w | R1 leaderboard · R2 model-not-seat · R3 conditions · R4 coherence · R5 does-deception-pay. | **blocked**: 335t judging + coherence metric |
| 6 | `06-discussion.md` | 400–600w | What it means for multi-agent deployment + model selection. | after §5 |
| 7 | `07-limitations.md` | 300–400w | The 6 mandatory caveats from `CLAIMS.md`. **Write early, honestly.** | ready |
| 8 | `08-broader-impact.md` | 200w | Safety framing; dual-use note. | ready |

## Figure plan (max ~5 in a workshop paper)

1. **Environment schematic** — the triple + turn loop. `TODO(make)`
2. **Model-not-seat** — `fig_model_not_seat.png` (H1a, strongest single figure)
3. **Condition contrast** — `fig_condition_contrast.png` (H2)
4. **Coherence over 335 turns** — `TODO(make)` (H3, the headline wedge)
5. **Does deception pay** — `fig_deception_pay_flagship.png` (H4)

Backups: `fig_type_by_model.png` (E1), `fig_campaigns.png` (H3 illustration).

## Drafting order

§7 Limitations → §3 Environment → §4 Method → §2 Related work → §1 Intro → *(gate: results land)* → §5 → §6 → §0 Abstract.

Rationale: the honest limitations first constrain every other claim; method/environment
are already fully determined by the code; results are the only data-blocked part.
