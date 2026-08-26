# Results

<!-- Drafted 2026-08-01 with the research-paper-writing skill (references/experiments.md).
     CONSTRAINT: every claim maps to a row in paper/CLAIMS.md and carries that row's caveat.
     Nothing marked NEEDS-DATA or DO-NOT-CLAIM appears here as a finding.
     Terminology locked to §3/§4: agent-turn, triple, verdict, episode, coherence, condition. -->

<!-- role: framing — sets the epistemic register for the whole section -->
We report six results, and we report them as observations rather than tests. Every run below
is a single game with a single seed, so no comparison here is significance-tested across
seeds; where we do use a p-value it is *within* a run, against a permutation null defined in
§4.4, and corrected for multiplicity. Our primary run is a ten-model free-for-all under the
neutral condition with blank personas, played for **335 social turns**, of which 1,601
agent-turns were judgeable and **1,600 were labelled** by the v2 judge (one turn is dropped:
the judge returned an unparseable verdict on four consecutive attempts, and we decline to
hand-label it because a human label would contaminate the judge's own label set).

## R1 — Models differ widely in deception propensity, but the ordering is roster-dependent (H1)

<!-- role: evidence -->
Deception rates across the nine scored models span the full available range, from 0% to 46%
of judged turns (Figure `fig_leaderboard_9model.png`): qwen 45.7%, gemini 26.3%, opus 23.4%,
gpt_5 23.0%, sonnet 17.6%, grok 10.0%, deepseek 7.1%, glm 6.2%, minimax 0.0%. The spread is
large enough that model identity is clearly doing work; the low end in particular is stable
across every run we have collected.

<!-- role: limitation — the honest correction to our own prior claim -->
The *specific* ordering we reported from earlier four-model games does not survive. In those
games GPT-5 sat at the bottom; here it is statistically indistinguishable from Opus (23.0% vs
23.4%) and above Sonnet. Gemini remains high and Grok remains low, so the extremes are more
robust than the middle. We therefore claim that models differ, and we decline to claim a
transitive cross-model ranking: **the ordering is roster-dependent**, and a leaderboard built
from one roster should not be quoted as a property of the models.

<!-- role: limitation — exposure -->
Exposure is badly unequal and the figure shows it beside the rates rather than relegating it
to a caption. Survival ranges from 36 turns (qwen) to the full 335 (gemini, gpt_5, sonnet), a
~9× spread. Rates are normalised per judged turn, but a short-lived agent is scored only on
early turns, when the economy is uncrowded and there is little accumulated trust to exploit.
Qwen's 45.7% — the highest rate in the run — rests on 35 judged turns and should not be read
as a stable property.

## R2 — Model, not seat (H1a)

Two instances of each model, given different specialties, rivals, and eventual fates, land in
the same band: Opus 39%/45%, Grok 0%/6% (Figure `fig_model_not_seat.png`). This is our
strongest single result because it is a *within-game* control — the two instances shared one
economy — but it is one game, and personas were confounded with models in that run.

## R3 — Emergence, not instruction (H2)

An honesty instruction lowers deception (all-model rate 24%→14%), while explicit permission to
deceive barely moves it (→25%), implying the competitive baseline already sits near the
behavioural ceiling that instruction can reach (Figures `fig_condition_contrast.png`,
`fig_type_mix_condition.png`). Instruction also changes the *kind* of deception, not only its
frequency: the honesty condition leaves only subtle omission and false-state claims, while the
permissive condition adds identity bluffs and false promises. n=1 per cell.

## R4 — Coherence: most of the campaign signal is arithmetic (H3, H3a)

<!-- role: the headline, stated as the negative result it is -->
Our primary contribution is a coherence metric, and its primary finding is a caution about
measuring coherence at all. Raw campaign statistics are **mechanically inflated**: with at
most nine rivals alive, an agent that tells 86 directed lies *must* repeat targets, so a high
"repeat-target share" measures lie volume divided by pool size rather than strategy. We
therefore evaluate every coherence statistic against a permutation null that holds each
deceiver's deceptive turns fixed and reshuffles only the *choice of victim* among agents alive
that turn (1,000 iterations, §4.4), and we correct across all 24 model×metric tests with
Benjamini-Hochberg.

<!-- role: evidence -->
The correction is not a formality. The four heaviest deceivers score **at or below chance** on
raw repeat-target share: gemini 0.870 vs a null mean of 0.884 (p=1.00), gpt_5 0.773 vs 0.838
(p=1.00), sonnet 0.882 vs 0.886 (p=0.80), opus 0.875 vs 0.851 (p=0.10). Four of 24 tests
survive at q≤0.05 (Figure `fig_coherence_335t.png`): above-chance target selectivity for two
*low-volume* deceivers, glm (0.750 vs 0.337, q=0.012) and grok (0.750 vs 0.157, q=0.016), and
above-chance contiguous campaign length for gemini (14 turns, q=0.012) and sonnet (12 turns,
q=0.042).

<!-- role: the negative result we are most obliged to state -->
The behaviour the metric was designed to capture — resuming a thread after a long silence —
is **not established by this run**. Opus returning to the same victim after 200 silent turns
is the most striking number we observed and it does not survive correction (p=0.018,
q=0.072); gemini's 149-turn return likewise fails (q=0.208). We report these as observations
and explicitly do not claim above-chance long-gap resumption.

<!-- role: limitation — the confound on the surviving result -->
Even the surviving episode-length result is confounded. The four longest campaigns all target
kimi, the agent excluded as a *deceiver* because it failed to emit valid tool calls on 56% of
its turns. Gemini's and Sonnet's long campaigns are therefore sustained against a functionally
impaired opponent that could neither retaliate nor update — behaviourally suggestive, since it
indicates deceivers concentrate on the weakest player, but partly an instrumentation artifact
rather than clean evidence of sustained deception against a competent adversary.

## R5 — Deception does not decay over the horizon; it intensifies late (H3e)

Pooled deception rate by 50-turn bucket runs 19.6%, 14.1%, 13.5%, 12.6%, **30.5%**, 29.8%,
24.5%, with a slightly *positive* overall slope (+0.0005/turn). The pre-registered expectation
that coherence would decay across a long horizon is not supported; deception dips through the
mid-game and then roughly doubles after turn ~200, as the field narrows from nine agents to
four. Two caveats bound this: the denominator collapses over the run (409 judged turns in the
first bucket, 102 in the last), and the late rise coincides with elimination pressure, so
intensity and survivorship are entangled. We report the pattern, not a mechanism.

## R6 — Whether deception pays is unresolved (H4)

<!-- role: honest tension between two runs -->
Our two runs disagree, and we report both. In the flagship game deception did not pay: the
apex winner deceived at 13% against a 26% field mean, and the heaviest deceivers finished near
broke (Figure `fig_deception_pay_flagship.png`). In the 335-turn run there is **no
relationship** between deception rate and survival (Spearman ρ=0.18, Pearson r=0.20, n=9), and
if anything the sign is mildly the other way: the three agents that survived all 335 turns
deceived at 18–26%, while the only model that never deceived at all (minimax, 0%) was
eliminated at turn 38. The one clear counter-case is qwen, the heaviest deceiver, eliminated
first at turn 36.

The honest reading is that these runs are underpowered for this question — nine points, one
seed, and outcomes heavily driven by environment RNG (§7). We state H4 as unresolved rather
than reporting whichever run we prefer.

## R7 — Judge reliability (M4)

Judge labels are self-consistent: with K=3 at temperature 0, three runs over a 120-turn
stratified sample agreed unanimously on 91.7% of turns. Against a different judge family
(GPT-5.2) on a prevalence-correct random sample of 120 turns, Cohen's **κ=0.50** (moderate)
with 87.5% raw agreement.

Two qualifications matter more than the pooled κ. First, **reliability tracks confidence**:
cross-judge agreement is 93.8% on turns where the primary judge reported confidence ≥0.90
(n=48) but only ~49% below it (n=72), so the labels are bimodal rather than uniformly noisy,
and the mean confidence of 0.85 should not be read as certifying the whole set. Second,
**absolute rates are judge-dependent** — GPT-5.2 labels 11.7% of turns deceptive against the
primary judge's 17.5% on identical turns. We therefore treat every rate in this section as a
within-judge quantity. We are not able to claim the leaderboard is judge-invariant: on the
random sample the top of the ordering is preserved but sonnet inverts, and with ~20 turns per
model those cells cannot resolve the question. Human validation is pending.
