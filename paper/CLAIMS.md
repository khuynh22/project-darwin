# Claim ledger

Every claim the paper might make, its evidence, and its status. **Nothing enters a
section without a row here.** Update the status as data lands — this file is the
defense against over-claiming, which is the main risk in this project.

**Status vocabulary**
- `SUPPORTED` — evidence in hand, survives the stated caveat; safe to assert.
- `DIRECTIONAL` — real signal, but n=1/underpowered; write as "we observe…", never "we show that models X".
- `NEEDS-DATA` — planned claim, evidence not collected. Must not appear as a finding.
- `DO-NOT-CLAIM` — occupied by prior work or refuted; explicitly avoid.

---

## Method / instrument claims

| # | Claim | Evidence | Status |
|---|---|---|---|
| M1 | The private/public/action **triple** enables *intent-grounded* deception labels (a lie, not just a false statement). | Judge validated on real traces; correctly spares honest aggression, flags concealed slander; grounded rationales. | **SUPPORTED** |
| M2 | An LLM judge over the triple produces calibrated, decisive verdicts. | 253 turns; conf. mean 0.83 / median 0.85 / min 0.60. | **SUPPORTED** |
| M3 | Intent-grounding adds signal over structural action flags. | 88% agreement, but 6 "judged-only" turns (pure public-message lies with no deception action). | **DIRECTIONAL** |
| M4 | Judge labels are reliable (self-consistency, judge-model sensitivity, human κ). | K=3 → 91.7% unanimous; vs GPT-5.2 → **κ=0.50** (moderate), 87.5% agreement on a prevalence-correct random sample. Human κ **still pending**. | **DIRECTIONAL** (2 of 3 legs done) |
| M4a | Judge reliability is **confidence-dependent**, not uniform. | Cross-judge agreement 93.8% on Opus-confidence ≥0.9 (n=48) vs ~49% below (n=72). | **SUPPORTED** |
| M4b | Absolute deception rates are **judge-dependent**. | GPT-5.2 labels 11.7% positive vs Opus 17.5% on identical turns. | **SUPPORTED** — never quote a rate as judge-invariant |
| M4c | The model *ranking* is judge-invariant. | Random sample n≈20/model: top preserved (opus>gemini) but **sonnet inverts** (.100→.250). Cells far too small. | **NEEDS-DATA** — needs the 2nd judge over all 1601 rows (~$14) |

## Empirical claims

| # | Claim | Evidence | Status |
|---|---|---|---|
| **H1** | Models differ systematically in deception propensity. | 9-model/335-turn run: qwen .46, gemini .26, opus .23, gpt_5 .23, sonnet .18, grok .10, deepseek .07, glm .06, minimax .00. Spread is large and the low end is stable. | **DIRECTIONAL** (1 seed/cell) |
| H1-ord | The specific ordering **Opus/Gemini high, GPT-5/Grok low**. | **Partly contradicted.** GPT-5 ties Opus (.230 vs .234) in the 10-model run, having been "low" in the 4-model games. Grok stays low (.10); Gemini stays high (.26). | **DO-NOT-CLAIM** as previously worded — the *high* end is not stable across rosters; report the ordering as roster-dependent |
| H1a | The difference is the **model**, not seat/luck/specialty. | Flagship 2×/model: Opus 39%/45%, Grok 0%/6% — pairs cluster despite different games. | **SUPPORTED** (within-game; 1 game) |
| H1b | Persona is not the driver. | Flagship confounds persona with model; the 10-model run used blank personas. | **NEEDS-DATA** |
| **H2** | Deception is emergent from incentive, not instruction (honesty ↓; "may deceive" ≈ neutral). | Contrast: ALL 24%→14%→25%; Opus 46→23. | **DIRECTIONAL** (n=1/cell) |
| **H3** | Deception is sustained coherently over long horizons (campaigns, resumption after gaps). | Metric now defined + frozen (`app/coherence.py`) and tested against a permutation null. **Result is largely negative** — see `research/leaderboard_335t_20260726/coherence_report.md`. | **DIRECTIONAL, heavily qualified** |
| H3a | Raw campaign statistics are **mechanically inflated** by lie volume ÷ pool size; a permutation null is required. | Gemini .870 vs null .884 (p=1.00); GPT-5 .773 vs .838 (p=1.00); Sonnet .882 vs .886 (p=.80) — the heaviest deceivers are *at or below* chance. | **SUPPORTED** — this is the methodological contribution |
| H3b | Above-chance **target selectivity** exists. | GLM .750 vs .337 (q=.012); Grok .750 vs .157 (q=.016). Both are low-volume deceivers. | **SUPPORTED** (1 seed) |
| H3c | Above-chance **contiguous campaigns** exist. | Gemini max len 14 (q=.012); Sonnet 12 (q=.042). | **DIRECTIONAL** — confounded: the 4 longest episodes all target Kimi, the tool-call-impaired agent |
| H3d | Deception is **resumed after long gaps** above chance. | Opus 200-turn return, p=.018 → **q=.072, fails BH-FDR** across 24 tests. Gemini q=.208. | **DO-NOT-CLAIM** — the designed headline did not survive its own null |
| H3e | Coherence **decays** over a long horizon. | Pooled rate 19.6→14.1→13.5→12.6→**30.5**→29.8→24.5% by 50-turn bucket; overall slope **+0.0005**/turn. | **REFUTED as worded** — deception intensifies late as the field narrows (entangled with survivorship) |
| **H4** | Deception is not adaptive — deceivers don't win. | Flagship: apex winner GPT-A 13% vs field 26%; heaviest liars near-broke. 335t: aggressors eliminated early. | **DIRECTIONAL** |
| E1 | Models differ in deception **style**, not just rate (Opus=false_state_claim; Gemini=identity_bluff/false_promise). | Pooled type mix. | **DIRECTIONAL** |
| E2 | Deception targets the perceived leader. | Most-targeted = wealth leader in 3/4 games. | **DIRECTIONAL** |

## Novelty claims (vs. prior art)

| # | Claim | Status |
|---|---|---|
| ~~N1~~ | ~~No prior work combines open adversarial economic survival + mixed-model + long horizon + the intent-grounded triple.~~ | **DO-NOT-CLAIM as worded** — Emergence World (arXiv 2606.08367, Jun 2026) has economic survival + mixed-model + long horizon. See `docs/research/2026-08-01-prior-art-resweep.md`. |
| N1′ | No prior work labels deception in such a setting from the **intent-grounded triple**; the nearest neighbour validates claims against the *ledger* and states it does "database confirmation rather than intent modeling". | **SUPPORTED** (re-sweep 2026-08-01) |
| N2 | First intent-grounded deception measurement among *competing peers* (vs Apollo's single-agent-vs-overseer; vs asymmetric sender/receiver dyads in arXiv 2510.12826). | **SUPPORTED** (re-sweep 2026-08-01) |
| N3 | Sustained deception **coherence** over hundreds of social turns is an unowned metric. | **SUPPORTED** as a gap — strengthened: the nearest neighbour explicitly does not analyse strategy persistence or resumption after interruption. Metric now **defined and frozen** (see H3). |
| — | "We are novel for having an economy" | **DO-NOT-CLAIM** (Sid, Sugarscape, Survival Games) |
| — | "First long-horizon **mixed-model** multi-agent economy" | **DO-NOT-CLAIM** (Emergence World, arXiv 2606.08367 — 4 vendors in one world, 15 simulated days) |
| — | "First cross-model deception tournament" | **DO-NOT-CLAIM** (The Traitors) |
| — | "First CoT-vs-action deception method" | **DO-NOT-CLAIM** (Apollo) |
| — | "First to study long-horizon deception" | **DO-NOT-CLAIM** (LH-Deception) |

## Mandatory caveats (must appear in Limitations)

1. n=1 per condition/cell; no significance testing yet. Bar is ≥20 seeds/condition.
2. The "neutral" prompt is an *aggressive survival* prompt that permits manipulation → claim **capability + propensity**, not unprompted misalignment.
3. Monologue is **stated** reasoning, not cognition (unfaithful-CoT).
4. Judge is an LLM; Opus judges Opus → self-preference risk unmeasured until M4.
5. 10-model run: KIMI excluded (56% tool-call fallbacks); judged from export, not full DB ground truth.
6. Environment RNG (specialty, yields) confounds per-agent outcomes.
7. **Unequal exposure.** Survival in the 10-model run spans 36–335 turns (~9×). Rates are
   exposure-normalised, but short-lived agents are scored only on early turns, and all
   long-horizon coherence is conditioned on survival — which is itself strategy-dependent.
8. **Kimi as preferred victim.** The longest campaigns target the agent that was impaired by
   tool-call fallbacks, so episode-length results are partly an instrumentation artifact.
9. **Multiplicity.** Coherence significance is reported after Benjamini-Hochberg FDR across
   all 24 model×metric tests. Uncorrected p-values must never be quoted as findings.
