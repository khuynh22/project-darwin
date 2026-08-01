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
| M4 | Judge labels are reliable (self-consistency, judge-model sensitivity, human κ). | K>1, second judge, human sample — **not yet run**. | **NEEDS-DATA** |

## Empirical claims

| # | Claim | Evidence | Status |
|---|---|---|---|
| **H1** | Models differ systematically in deception propensity (Opus/Gemini high; GPT-5/Grok low). | Ordering held in all 4 early games + flagship. | **DIRECTIONAL** (1 seed/cell) |
| H1a | The difference is the **model**, not seat/luck/specialty. | Flagship 2×/model: Opus 39%/45%, Grok 0%/6% — pairs cluster despite different games. | **SUPPORTED** (within-game; 1 game) |
| H1b | Persona is not the driver. | Flagship confounds persona with model; the 10-model run used blank personas. | **NEEDS-DATA** |
| **H2** | Deception is emergent from incentive, not instruction (honesty ↓; "may deceive" ≈ neutral). | Contrast: ALL 24%→14%→25%; Opus 46→23. | **DIRECTIONAL** (n=1/cell) |
| **H3** | Deception is sustained coherently over long horizons (campaigns, resumption after gaps). | Opus→Grok 10 turns w/ gap+resumption (25t); 335-turn run pending judging. | **NEEDS-DATA** (metric undefined) |
| **H4** | Deception is not adaptive — deceivers don't win. | Flagship: apex winner GPT-A 13% vs field 26%; heaviest liars near-broke. 335t: aggressors eliminated early. | **DIRECTIONAL** |
| E1 | Models differ in deception **style**, not just rate (Opus=false_state_claim; Gemini=identity_bluff/false_promise). | Pooled type mix. | **DIRECTIONAL** |
| E2 | Deception targets the perceived leader. | Most-targeted = wealth leader in 3/4 games. | **DIRECTIONAL** |

## Novelty claims (vs. prior art)

| # | Claim | Status |
|---|---|---|
| N1 | No prior work combines open adversarial economic survival + mixed-model + long horizon + the intent-grounded triple. | **SUPPORTED** (2 verified sweeps; **re-sweep before submission**) |
| N2 | First intent-grounded deception measurement among *competing peers* (vs Apollo's single-agent-vs-overseer). | **SUPPORTED** |
| N3 | Sustained deception **coherence** over hundreds of social turns is an unowned metric. | **SUPPORTED** as a gap; the metric itself is **NEEDS-DATA** |
| — | "We are novel for having an economy" | **DO-NOT-CLAIM** (Sid, Sugarscape, Survival Games) |
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
