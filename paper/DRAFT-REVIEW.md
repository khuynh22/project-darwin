# Draft review — pass 1 (§1, §3, §4)

Produced with the `research-paper-writing` skill output contract. Covers the sections drafted
2026-07-26: §3 Environment, §4 Method, §1 Introduction. (§2 and §7 were drafted earlier;
§5, §6, §0 remain gated on results.)

## Reverse outline

**Thesis.** Deception among competing LLM agents can be measured *intent-grounded* and
*over long horizons* in an open survival economy — and doing so reveals model-specific,
incentive-driven deception that prior output-only, single-agent, or short-horizon evaluation
cannot see.

| § | Paragraph topic sentence (compressed) | Maps to thesis via |
|---|---|---|
| 1.1 | LLM agents are deployed multi-agent, autonomous, long-horizon → peer deception is an unaddressed risk. | establishes the problem |
| 1.2 | Deception is defined by intent, but evaluation observes behaviour. | names the core difficulty |
| 1.3 | Prior work supplies ingredients, never the combination. | positions the gap |
| 1.4 | The unmet challenge = intent-grounded + peer-directed + sustained, for 3 technical reasons. | defines what must be built |
| 1.5 | Environment + triple + judge → intent-grounded labels among peers. | contribution 1 |
| 1.6 | Episodes + coherence → deception over the horizon. | contribution 2 |
| 1.7 | Single-seed observations, hedged. | evidence |
| 1.8 | Four contributions. | summary |
| 1.9 | Scope: propensity-under-incentive; stated reasoning; single-seed. | honesty guard |
| 3.0 | Overview: open adversarial survival economy, and a map of 3.1–3.5. | sets the instrument |
| 3.1 | Economy supplies the *incentive* to deceive. | prerequisite for elicitation |
| 3.2 | Action space supplies the *means*, with agent-authored deceptive content. | prerequisite for elicitation |
| 3.3 | Information asymmetry makes lying *pay*. | prerequisite for elicitation |
| 3.4 | The triple makes deception *measurable*. | the core asset |
| 3.5 | Conditions + seeding make it *controlled*. | validity |
| 4.0 | Overview: labels → metrics, offline and versioned. | sets the pipeline |
| 4.1 | Deception = channel contradiction; two exclusions; five types. | the definition |
| 4.2 | The judge applies it with ground truth and quoted evidence. | the instrument |
| 4.3 | Normalization enforces label invariants. | data hygiene |
| 4.4 | Four metric families; coherence is the contribution. | what we measure |
| 4.5 | Reliability protocol. | why labels are trustworthy |

**Result:** every paragraph maps cleanly. No orphan paragraphs found.

## Self-review checklist

| dimension | status |
|---|---|
| **Clarity** — one message/paragraph, message in first sentence | ✅ Verified for all new paragraphs. |
| **Flow** — each sentence relates to the prior (cause/contrast/consequence/refinement) | ✅ §1.3→1.4 uses explicit contrast; §4.1→4.2 uses consequence. |
| **Terminology consistency** | ✅ *agent-turn*, *the triple*, *the Oracle*, *condition*, *episode*, *coherence*, *intent-grounded*, *major/free action* used verbatim across §1/§3/§4. No synonym drift (never "round"/"tick" for turn; never "verdict" for "label" except as the typed object). |
| **Unsupported claims** | ⚠️ §1.7 is hedged with `TODO(data)` and "single-seed observations, not significance-tested". Must be re-checked against §5 when results land. |
| **Missing evidence** | ⚠️ Two known gaps, both flagged in-text: the coherence statistic is not finalized (§4.4) and the reliability numbers are not collected (§4.5). |
| **Figures** | ⚠️ Figure 1 (turn-loop + triple schematic) is `TODO(make)` and is referenced from §3.0. |

## Claim–evidence map

Claims asserted in the drafted text, checked against `CLAIMS.md`.

| Claim (as written) | Evidence | Status |
|---|---|---|
| Deception can be labelled by contradiction among private intent, public message, and executed action. | Judge validated on real traces; spares honest aggression, flags concealed slander (`CLAIMS.md` M1). | **supported** |
| The judge produces calibrated, auditable verdicts. | 253 turns; confidence mean 0.83 / median 0.85 / min 0.60 (M2). | **supported** |
| Deceptive content is agent-authored, not templated. | Slander/gaslight payloads are model-written, varied, state-aware; verified in calibration. | **supported** |
| Intent-grounding adds signal over action-level flags. | 88% agreement with structural flags, 6 judged-only turns (M3). | **needs evidence** (directional; n=1) |
| Deception rates separate consistently by model. | Ordering held across 4 early games + flagship (H1). | **needs evidence** (single seed; written as observation only) |
| Two instances of the same model deceive at comparable rates while different models do not. | Flagship 2×/model: Opus 39%/45%, Grok 0%/6% (H1a). | **supported** (within-game control, one game) |
| An honesty instruction lowers deception; permission barely raises it. | Condition contrast 24%→14%→25% (H2). | **needs evidence** (n=1/cell) |
| The most deceptive agents gained no wealth or survival advantage. | Flagship apex winner 13% vs 26% field mean; 335-turn eliminations (H4). | **needs evidence** (RNG-confounded; written as "in the games observed") |
| Coherence can be computed over hundreds of turns. | Episode reconstruction implemented; 335-turn run collected but **not yet labelled** (H3). | **needs evidence** — stated as a *capability*, never as a finding |
| No prior work combines intent-grounding, peer competition, open economy, and long horizon. | Two verified prior-art sweeps (N1/N2/N3). | **supported** — re-sweep before submission |
| Reliability is established via self-consistency, judge sensitivity, human κ. | Protocol specified only (M4). | **needs evidence** — written in future//specification voice |

**Rule applied:** every `needs evidence` row is phrased in the draft as an observation, a
capability, or a specification — never as a demonstrated result. Re-audit this table when §5
is written.

## Next actions for these sections

1. Make Figure 1 (turn loop + triple schematic) — referenced but missing.
2. After Phase 0 judging: replace the `TODO(data)` in §1.7 with concrete numbers, then re-run
   this claim map and upgrade statuses.
3. After Phase 1: replace the `TODO(finalize)` in §4.4 with the adopted coherence statistic and
   name the rejected candidates.
4. Before submission: run `references/paper-review.md` five-dimension adversarial review across
   the full draft.
