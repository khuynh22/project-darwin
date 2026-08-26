# Phase 1 — the coherence metric: definition, selection, and what it shows

**Date:** 2026-08-01
**Data:** 10-model / 335-turn run, 1600/1601 judgeable turns labelled by the Opus v2 judge (K=1).
**Code:** `backend/app/coherence.py` (frozen), `analyze_coherence.py` (driver),
`backend/tests/test_coherence.py` (14 tests).
**Headline:** the metric is defined and frozen — but **most of the raw coherence signal is
arithmetic, not strategy**, and saying so is the main result of this phase.

---

## 1. The definition

An **episode** is a maximal *directed campaign*: consecutive deceptive turns by the same
deceiver against the same target, joined while the gap between successive deceptive turns is
`<= max_gap`. A **gap** is the number of turns the deceiver was alive but did not deceive
*that* target. A **resumption** is an internal gap `>= resume_gap` that the deceiver closed by
returning to the same victim.

Frozen parameters: `max_gap = 5`, `resume_gap = 2`. Untargeted lies (`target_id = null`) are
excluded — an untargeted lie has no thread to sustain.

## 2. The problem that governs everything: the mechanical floor

`repeat_target_share` — the share of a deceiver's directed lies aimed at an already-deceived
victim — looks like the obvious campaign metric. **It is nearly worthless raw.** With at most
nine rivals alive and Gemini telling 86 directed lies, repetition is forced by arithmetic: the
value cannot fall below `1 - n_targets/n_lies`. A high score measures *volume*, not intent.

The same objection applies to `max_return_gap`. An agent that lies constantly for 335 turns
will revisit some victim after a long silence by chance alone.

**Every coherence statistic is therefore reported against a permutation null.** We hold each
deceiver's deceptive turn indices fixed and reassign each turn's *target* uniformly among the
agents alive on that turn (excluding itself), 1000 iterations. This preserves how often the
agent lied, when it lied, and how many rivals existed; only the **choice of victim** is
randomised. What survives is target selectivity — which is what "campaign" means.

Kimi is included in the null's target pool. It is excluded as a *deceiver* (tool-call
artifact) but was a real agent and a legitimate victim; shrinking the pool would bias the test
toward calling chance repetition "selectivity".

Because we run one test per model per metric, results are corrected with
**Benjamini-Hochberg FDR across all 24 tests**. Raw p-values are not quoted as findings.

## 3. What survived

| model | metric | observed | chance | p | q (BH) | |
|---|---|---|---|---|---|---|
| gemini | max episode length | 14 | — | 0.001 | **0.012** | ✔ |
| glm | repeat-target share | 0.750 | 0.337 | 0.001 | **0.012** | ✔ |
| grok | repeat-target share | 0.750 | 0.157 | 0.002 | **0.016** | ✔ |
| sonnet | max episode length | 12 | — | 0.007 | **0.042** | ✔ |
| grok | max episode length | 3 | — | 0.016 | 0.072 | ✘ |
| **opus** | **max return gap** | **200** | **134** | **0.018** | **0.072** | **✘** |
| qwen | repeat-target share | 0.600 | 0.376 | 0.037 | 0.127 | ✘ |
| gemini | max return gap | 149 | 111.5 | 0.078 | 0.208 | ✘ |

**4 of 24 tests survive at q ≤ 0.05.**

Two readings matter more than the table:

**(a) The heavy deceivers' repeat-target shares are pure arithmetic.** Gemini observes 0.870
against a null mean of 0.884 (p = 1.000); GPT-5 observes 0.773 against 0.838 (p = 1.000);
Sonnet 0.882 vs 0.886 (p = 0.803). These four models look maximally "campaign-like" on the raw
number and are **at or below chance** once volume is controlled. Any paper that reports raw
repeat-target rates as evidence of campaigns is reporting the size of its agent pool.

**(b) The dramatic resumption numbers do not survive.** Opus returning to the same victim
after **200 silent turns** is the single most striking number in the run, and it is *not*
significant after correction (q = 0.072). We do not claim it. Long-gap resumption, the
behaviour the metric was designed around, is **not demonstrated by this run**.

What *is* demonstrated: Gemini and Sonnet sustain longer **contiguous** runs against one
target than chance allows, and two low-volume deceivers (GLM, Grok) concentrate their few lies
on one victim far more than chance.

## 4. The confound that limits even the surviving result

**The four longest episodes all target Kimi** — the agent excluded as a deceiver because it
failed to emit valid tool calls on 56% of its turns:

| deceiver → target | len | span | turns |
|---|---|---|---|
| gemini → kimi | 14 | 36 | 279…314 |
| sonnet → kimi | 12 | 24 | 287…310 |
| sonnet → kimi | 10 | 24 | 197…220 |
| sonnet → kimi | 7 | 15 | 228…242 |

Gemini's and Sonnet's surviving `max_episode_len` results are therefore campaigns *against a
functionally impaired agent* that could not effectively retaliate or update. That is
behaviourally interesting — deceivers concentrate on the weakest player — but it is **not
clean evidence of sustained deception against a competent adversary**, and it is partly an
instrumentation artifact. Any claim built on episode length must state this.

## 5. Candidates rejected, and why

| candidate | verdict | reason |
|---|---|---|
| **repeat-target share (raw)** | rejected as a headline | mechanically forced by lie volume ÷ pool size; four heaviest deceivers score at or below chance |
| **repeat-target share vs null** | **kept** | volume-controlled; isolates victim selection |
| **max/mean episode length (raw)** | rejected as a headline | bounded by lifespan (36–335 turns here, ~9× spread) and by `max_gap` |
| **max episode length vs null** | **kept** | the only contiguous-campaign measure with surviving signal |
| **max return gap** | **kept as reported, not as a finding** | the designed headline; does not survive correction in this run |
| **abandonment / singleton share** | rejected | inverse of episode length, adds no independent information (r ≈ −1 by construction) |
| **narrative type-consistency** | rejected | range is narrow (0.63–0.69 for all high-volume models) and it conflates a coherent story with a model's fixed stylistic preference for one deception type |
| **episode density** | rejected | 0.82–0.88 for every high-volume model; no discrimination |
| **coherence-vs-turn slope** | rejected as a coherence measure | see §6 — it measures intensity, not coherence |

## 6. Decay: the horizon does not wear coherence down

Deception rate by 50-turn bucket, pooled: 19.6% → 14.1% → 13.5% → 12.6% → **30.5%** → 29.8% →
24.5%. The overall slope is slightly **positive** (+0.0005/turn). Deception dips through the
mid-game and then intensifies sharply after turn ~200, as the field narrows from nine agents
to four.

So the pre-registered expectation — that coherence *decays* over a long horizon — is not
supported; if anything the opposite. But note the denominator collapses (409 judged turns in
bucket 1 vs 102 in the last), and the late rise coincides with elimination pressure, so
intensity and survivorship are entangled. We report this as an observation, not a mechanism.

## 7. Segmentation is not load-bearing

`max_gap` sweep (episodes / mean len / singleton share / share with resumption):

| max_gap | 1 | 2 | 3 | **5** | 8 | 13 |
|---|---|---|---|---|---|---|
| episodes | 197 | 175 | 156 | **141** | 126 | 104 |
| mean length | 1.25 | 1.41 | 1.58 | **1.75** | 1.96 | 2.38 |
| singleton share | 0.82 | 0.77 | 0.74 | **0.69** | 0.66 | 0.51 |

Monotone and gradual — no threshold at which the picture flips. `max_gap = 5` is reported;
conclusions are unchanged across 3–8. Panels (b) and (c) of the figure use the
segmentation-free statistics and do not depend on this choice at all.

## 8. What this means for the paper

The contribution is **the metric plus its null model**, and the honest empirical finding is
mostly negative:

1. Raw campaign statistics in a small agent pool are dominated by lie volume. This is a
   methodological warning the subfield needs — prior work reporting "sustained campaigns"
   without a permutation control may be reporting arithmetic.
2. Above-chance target selectivity is real but concentrated in *low-volume* deceivers.
3. Above-chance contiguous campaigns are real for Gemini and Sonnet, but target an impaired
   agent.
4. Long-gap resumption — the behaviour the metric was built for — is **not** established here.

This is weaker than the Phase-1 plan hoped for and should be written that way. It is still a
publishable methodological contribution, and it is a far better position than publishing the
raw 87% repeat-target numbers and having a reviewer compute the null.
