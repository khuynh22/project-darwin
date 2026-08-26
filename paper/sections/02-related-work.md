# Related work

*(Rule: we own the **measurement**, never the setting. Each subsection names what the work
established and precisely where it stops. Re-verified 2026-08-01 —
`docs/research/2026-08-01-prior-art-resweep.md`; the closest works are recent and the area
moves at roughly one near-neighbour per two months, so re-verify again before submission.)*

**Deception in LLM agents.** The field measures deception either from outputs alone or by
triangulating a private channel against behaviour, and only the latter can distinguish a lie
from an honest mistake. @traitors2025 is nearest on metrics — a ten-agent social-deduction
game with a named metrics suite and cross-model comparison — but has no private-reasoning
channel, no economy, homogeneous populations, and self-describes n=10 as underpowered.
@apollo2024 supplies our methodological anchor, establishing *intentional* deception by
triangulating chain-of-thought against action, yet studies a single agent against an
overseer rather than a peer economy. @park2023 defines deception functionally and names
detection tooling as an open problem. We adopt Apollo's triangulation and move it from the
single-agent-vs-overseer setting into a population of competing peers. `TODO(cite)`
unfaithful-CoT.

**Deception among peers.** Work that puts models against each other still tends to fix an
asymmetric pair of roles, which bounds how long any one deceptive relationship can run.
@scheming2026 compares four models but in asymmetric dyads (sender/receiver,
evaluator/evaluatee) with no fixed horizon, and concedes that multi-turn coherence is not
analysed systematically. @aitoai2026 tests six models, each separately against a *fixed*
subordinate, over at most twelve turns; its headline coercion score is **self-reported** by
the model against a nine-rung rubric with no judge in the scoring path, and each conversation
is treated as independent. Neither setting lets a deceiver choose its own victim from a field
of rivals, which is the precondition for the campaign structure we measure.

**Long-horizon deception.** Long-horizon work measures either task completion or
output-level deception, but not deception that must stay consistent to keep working.
@lhdeception2026 remains the closest on framing — deception across long-horizon
interactions, eleven frontier models, n=20 — but differs on four axes: cooperative hierarchy
(performer→supervisor) rather than adversarial peers; ~42 rounds; deception scored by a
post-hoc auditor over **outputs only**, so not intent-grounded; and no economy or survival
pressure. The broader long-horizon literature (@metr2025, @ultrahorizon2025, @odyssey2025)
measures single-agent task completion in tokens and tool calls, not **social turns**. Goal
drift is instrumented by @apollodrift2025, again single-agent.

**Multi-agent economies and emergence.** The environment we use is not novel, and we do not
claim it. @emergenceworld2026 is the nearest neighbour overall: a ten-agent economy with
energy and compute-credit scarcity, governance votes, a **heterogeneous world mixing four
vendors**, run for fifteen continuous simulated days. It therefore occupies the combination
of economic survival, mixed-model population, and long horizon outright. Its deception
labels, however, come from an LLM classifier over speech and diary entries **validated
against the ledger** — the authors describe this as "database confirmation rather than intent
modeling" — and it reports temporal bursts and cumulative counts without analysing whether
an agent sustained a strategy across interactions or resumed one after interruption. That is
the seam we work in. @conscientia2026 likewise shows emergent deception and trust erosion at
scale (250 agents, repeated steering driving susceptibility to 93.9%) but is single-model and
scores deception by *action divergence*, never from private reasoning. @sid2024 demonstrates
emergent roles and culture and **already includes an economy with taxation**; @sugarscape2025
shares survival-with-elimination and pioneers the emergent-vs-instructed contrast we adopt
for conditions, but has no market, no private channel, and no deception measurement.
@concordia2023 provides a game-master architecture akin to our Oracle, targeting
explainability rather than deception metrics.

**Game-theoretic evaluation.** Cross-model strategic tournaments are established but
fixed-form. @gtbench2024 runs ten games with predetermined action spaces and endpoints, and
@econagent2024 anchors the LLM behavioural-economics lineage. Neither measures deception, and
the fixed matrix removes the open-ended target selection that campaigns require.

**Positioning.** Our contribution is a *measurement*, not an environment. Given a
long-horizon mixed-model economy — which @emergenceworld2026 also built — two things remain
unowned: labelling each turn from the **intent-grounded triple** of stated private reasoning,
public message, and actual action against ground truth, so that a lie is separated from an
honest error and from honest aggression; and quantifying **coherence**, whether a deceiver
sustains a directed campaign against a chosen victim and resumes it after silence. Every
work above either measures deception without the private channel, or has the private channel
without competing peers, or has both without a long enough horizon for a campaign to exist.
