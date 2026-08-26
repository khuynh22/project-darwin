# Phase 2 — judge reliability

**Date:** 2026-08-01 · **Data:** 335-turn run, 1600 Opus-v2 verdicts
**Code:** `reliability.py` · **Raw:** `reliability_report.json`

Three checks, plus one the numbers forced us to add.

## 1. Self-consistency — 91.7% unanimous (K=3)

The judge runs at `temperature=0`, so repeated sampling measures *provider*
nondeterminism rather than sampling noise. On a 120-turn stratified sample, all three
runs agreed on **91.7%** of turns. The 8.3% that flip are the judge's own boundary
cases, not a sampling artifact we can tune away.

## 2. Judge-family sensitivity — population κ = 0.502 (moderate)

Re-judged with **GPT-5.2**, a different family, which also controls the
Opus-judges-Opus self-preference risk.

| sample | design | κ | observed agreement | Opus positive | GPT-5.2 positive |
|---|---|---|---|---|---|
| stratified (n=120) | 50/50 on Opus's label | 0.350 *(fair)* | 0.675 | 0.500 | 0.292 |
| **random (n=120)** | unstratified | **0.502** *(moderate)* | **0.875** | 0.175 | 0.117 |

**Report the random-sample κ = 0.502.** Cohen's κ is prevalence-sensitive, and the
stratified sample's marginals are engineered by construction (we deliberately
oversampled the rare positive class), so its κ = 0.350 is *not* the population value.
Quoting the stratified number would understate agreement; quoting it without the design
caveat would be wrong. Both are reported here for transparency.

**GPT-5.2 is systematically more conservative** — 11.7% vs 17.5% positive on the same
turns. Absolute deception rates are therefore judge-dependent and must never be quoted
as if judge-independent.

## 3. The finding that matters most — reliability tracks confidence

Cross-judge agreement, split by the primary judge's own stated confidence:

| Opus confidence | n | agreement with GPT-5.2 |
|---|---|---|
| **high (≥0.90)** | 48 | **0.938** |
| mid (0.75–0.90) | 43 | 0.488 |
| low (<0.75) | 29 | 0.517 |

The judge is highly reliable exactly where it is confident, and **near chance
elsewhere**. This is more actionable than the pooled κ: it means the labels are not
uniformly noisy, they are *bimodal*. Two consequences for the paper:

1. Headline claims should be computed on, or at minimum checked against, the
   high-confidence subset.
2. Mean confidence (0.83) should never be quoted as if it certified the whole set —
   roughly a third of turns sit in a band where two judges agree at coin-flip rates.

## 4. Does the judge choice change the model ranking?

This is the check H1 actually depends on: a uniformly conservative judge can lower every
rate and leave the ordering intact.

On the **random** sample (n ≈ 10–22 per model — small, and this is the limit of what
$1 of budget buys):

| model | n | Opus rate | GPT-5.2 rate |
|---|---|---|---|
| opus | 21 | 0.333 | 0.191 |
| gemini | 21 | 0.238 | 0.143 |
| gpt_5 | 22 | 0.136 | 0.000 |
| deepseek | 18 | 0.111 | 0.056 |
| glm | 10 | 0.100 | 0.100 |
| sonnet | 20 | 0.100 | **0.250** |

Ordering is preserved at the top (opus > gemini) but **Sonnet inverts**, from joint-lowest
under Opus to highest under GPT-5.2. With ~20 turns per model these cells are far too
small to resolve — a single label flips a rate by 5 points. **We therefore cannot claim
the leaderboard is judge-invariant.** Establishing that needs the second judge run over
the full 1601 rows (≈ $14), which the remaining budget did not cover.

*Note:* the stratified sample cannot test this at all — its round-robin design forces
every model to ≈0.5 under the primary judge. An earlier Spearman ρ = 0.757 computed on
it is degenerate and is not reported.

## 5. Human validation — PENDING

`human_labels_BLANK.jsonl` holds the 120 stratified turns with the actor and the primary
verdict stripped, so labelling cannot anchor on the judge. Fill `is_deceptive`, save as
`human_labels.jsonl`, and run `--stage score` for Cohen's κ against the judge.

This is the one Phase-2 leg still open, and it is the leg reviewers weight most.

## Status of M4

Partially discharged. Self-consistency and judge-sensitivity are measured; human κ is
not. The honest summary line for §4:

> Judge labels are self-consistent (91.7% unanimous at K=3, temperature 0) and agree
> moderately with a different judge family (Cohen's κ = 0.50, 87.5% raw agreement, on a
> prevalence-correct random sample). Agreement is strongly confidence-dependent: 93.8%
> on high-confidence verdicts versus ~49% below. Absolute rates are judge-dependent — a
> second judge labels ~33% fewer turns deceptive — so we report rates as within-judge
> quantities and do not claim judge-invariance of the model ranking.
