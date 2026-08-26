# Abstract

<!-- Drafted 2026-08-01 with the research-paper-writing skill (references/abstract.md).
     HARD CONSTRAINT: every sentence must be defensible from paper/CLAIMS.md. The
     coherence result is largely negative and the abstract must say so — an abstract
     that outruns the ledger is the main rejection risk for this paper. -->

Autonomous language-model agents are increasingly deployed in populations that run for long
horizons, yet deception is still mostly evaluated on single agents, under instruction, and one
turn at a time. We study deception among *competing peers*: three to ten frozen frontier models
share an open survival economy with progressive taxation, hunger, and permanent elimination,
and are told only to survive. Every agent-turn is recorded as a **triple** — the agent's stated
private reasoning, the message it broadcasts, and the action the engine actually applied
against ground truth — which lets an offline judge label a turn deceptive only when those
channels contradict, separating a lie from an honest error and from openly aggressive play.
Judge labels are self-consistent (91.7% unanimous at K=3) and agree moderately with a different
judge family (Cohen's κ=0.50, 87.5% agreement); agreement is 93.8% on high-confidence verdicts
but near chance below, so we treat rates as within-judge quantities.

In a ten-model, 335-turn game (1,600 judged turns) deception rates span 0–46% and separate
sharply by model, though the ordering is roster-dependent: a model that ranked lowest in our
four-model games ranks joint-highest here. We then ask whether deception is *sustained*, and
report a mainly cautionary answer. Raw campaign statistics are mechanically inflated — with few
rivals alive, a frequent liar must repeat targets — and against a permutation null the four
heaviest deceivers score at or below chance on target selectivity. Only 4 of 24 tests survive
multiplicity correction: above-chance target selectivity in two *low-volume* deceivers, and
above-chance contiguous campaigns in two models, though the longest campaigns all target an
instrumentation-impaired opponent. Long-gap resumption, the behaviour our metric was designed
to detect, is not established. Deception does not decay over the horizon; it roughly doubles
after turn 200 as the field narrows. All results are single-seed observations, not
significance-tested comparisons across seeds. We release the environment, the judged traces,
and the coherence metric with its null model, and we argue the null should be standard practice
for any multi-agent deception study drawing campaign structure from a small agent pool.
