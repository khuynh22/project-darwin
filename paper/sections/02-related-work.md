# Related work

*(Rule: we own the **integration**, never a single axis. Each subsection names what the
work established and precisely where it stops. Re-verify all before submission — the
closest works are recent and the area moves fast.)*

**Deception in LLM agents.** @traitors2025 is nearest on deception metrics: a ten-agent
social-deduction game with a named metrics suite and cross-model comparison. It has no
private-reasoning channel, no economy, homogeneous populations, and self-describes n=10 as
underpowered. @apollo2024 supplies our methodological anchor — establishing *intentional*
deception by triangulating chain-of-thought against action — but studies a single agent
against an overseer, not a peer economy. @park2023 defines deception functionally and names
detection tooling as an open problem. `TODO(cite)` unfaithful-CoT.

**Long-horizon deception.** @lhdeception2026 is the closest work overall and the main
scooping risk: deception across long-horizon interactions, eleven frontier models, n=20.
It differs on four axes: cooperative hierarchy (performer→supervisor) rather than
adversarial peers; ~42 rounds; deception scored by a post-hoc auditor over **outputs only**,
so not intent-grounded; and no economy or survival pressure. The broader long-horizon
literature (@metr2025, @ultrahorizon2025, @odyssey2025) is single-agent task completion
measured in tokens and tool calls, not **social turns**. Goal drift is instrumented by
@apollodrift2025 but again single-agent.

**Multi-agent social simulation.** @sid2024 demonstrates emergent roles and culture and
**already includes an economy with taxation** — so an economy is not our novelty; its own
stated gap is that agents lack survival drives, and deception is incidental. @concordia2023
provides a game-master architecture akin to our Oracle but targets explainability, not
deception metrics. @sugarscape2025 shares survival-with-elimination and cross-model
aggression differences, and pioneers the emergent-vs-instructed design we adopt for
conditions — but uses an energy grid with no market, no deception measurement, and no
private channel.

**Game-theoretic evaluation.** @gtbench2024 establishes cross-model strategic tournaments
across ten **fixed-form** games with predetermined action spaces and endpoints;
@econagent2024 anchors the LLM behavioral-economics lineage. We found no prior work running
an **open-ended** (non-fixed-matrix) multi-agent economic-survival game measuring
cross-model cooperation and betrayal.

**Positioning.** Each axis — economy, cross-model tournaments, CoT-vs-action deception,
long-horizon framing — is individually occupied. What is unoccupied is their intersection:
intent-grounded deception among *competing, mixed-model* peers in an *open* survival
economy, sustained over *hundreds of social turns*, together with a metric for that
sustained coherence.
