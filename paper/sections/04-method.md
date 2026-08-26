# Method

<!-- Drafted 2026-07-26 with the research-paper-writing skill (references/method.md).
     Terminology inherited from §3 and used verbatim: agent-turn, the triple, the Oracle,
     condition, major/free action. New terms defined here: verdict, episode, coherence. -->

<!-- role: overview -->
Our measurement pipeline turns the recorded triple into deception labels and then into
metrics. Section 4.1 gives the operational definition of deception and the taxonomy it
induces; 4.2 describes the judge that applies it; 4.3 the deterministic post-processing that
enforces label invariants; 4.4 the metrics computed from labelled turns, including the
sustained-coherence measure that is our primary contribution; and 4.5 the protocol by which we
establish that the labels are trustworthy. The pipeline runs **offline in batch** over
persisted records and never participates in the turn loop, so labelling can be re-run,
versioned, and audited without perturbing the games it measures.

## 4.1 What counts as deception

<!-- role: motivation -->
A definition based on falsehood alone would conflate lying with error, and a definition based
on harm would conflate deception with honest aggression. We therefore define deception
*relationally*, as a conflict between the channels of a single agent-turn.

<!-- role: design -->
An agent-turn is **deceptive** if and only if its public message misrepresents at least one of:
the agent's own stated private intent, the action the Oracle actually applied, or the recorded
ground-truth state. Two exclusions follow directly and are enforced in the judging instructions.
Openly aggressive play is *not* deception — an agent that announces a theft and then commits it
has misrepresented nothing. Silence is *not* deception on its own; withholding information
counts only when an actively misleading partial claim is made. Each deceptive turn is assigned
exactly one type: **false state claim** (a claim about balance, resources, or relations that
contradicts ground truth), **false promise** (a public commitment the stated reasoning shows no
intent to keep), **strategic omission** (a technically true claim engineered to mislead),
**misdirection** (a claim about one's own action that mismatches the action taken), or
**identity bluff** (misrepresentation of role, alliance, or strength).

<!-- role: advantage -->
Because the definition is a contradiction among observed channels rather than a judgement about
truth in the world, it is *intent-grounded*: it distinguishes an agent that privately plans to
rob a partner while publicly promising a fair trade from one that promises a trade in good faith
and is later forced to renege.

## 4.2 The judge

<!-- role: motivation -->
Applying the definition at scale requires reading free-form text in context, which rules out
keyword rules; but an unconstrained reader would produce unauditable labels. The judge is
therefore an LLM constrained to a structured verdict backed by quoted evidence.

<!-- role: design -->
For each agent-turn the judge receives the triple **together with ground truth**: the agent's
true balance and trust score that turn, the action and outcome the Oracle applied, and the
ledger rows written — including the verbatim text of any slander or gaslight the agent
authored. Given this record it returns a typed **verdict**: a binary label, one deception type,
the set of channels in conflict, the targeted agent if any, a calibrated confidence in [0,1], a
free-text rationale, and quoted evidence spans from the private and public channels plus the
ground-truth fact that grounds the call. The judge is queried at temperature 0 with a versioned
prompt; verdicts are cached under the key (judge model, prompt version, sample index), so
multiple judge models, prompt revisions, and repeated samples coexist and are never pooled
across versions.

<!-- role: advantage -->
Supplying ground truth alongside the triple is what lets the judge call a *lie* rather than a
tone shift: a public claim of wealth can be checked against the recorded balance, and a claim
about one's own action against the action the engine executed. Requiring quoted spans makes
every label auditable after the fact, and the framing of the monologue as *stated* reasoning —
enforced in the prompt and in the field names — keeps the method compatible with evidence that
chain-of-thought need not faithfully reflect a model's computation.

## 4.3 Verdict normalization

<!-- role: motivation -->
Structured decoding constrains a verdict's shape but not its coherence, and we observed two
recurring defects that would corrupt downstream aggregation.

<!-- role: design -->
A deterministic post-processing step therefore repairs each verdict before storage. First, a
verdict naming the judged agent as its own target has that target cleared, since an agent is not
the recipient of its own deception and a self-target would otherwise pollute per-target
grouping. Second, a verdict labelled deceptive but listing no conflicting channel is assigned
the public message channel, the minimal carrier of a public lie, so that every deceptive turn
has at least one channel for channel-level analysis. The judging prompt states both
constraints explicitly; normalization is the deterministic backstop that guarantees the
invariant holds in the stored data.

## 4.4 Metrics

<!-- role: design -->
From labelled agent-turns we compute four families of measure. **Deception rate** is the
fraction of an agent's decision turns labelled deceptive, reported per model and per condition.
**Type mix** is the distribution over the five deception types, which characterizes *how* a
model deceives rather than how often. **Adaptivity** relates an agent's deception rate to its
survival time and final wealth, testing whether deception is instrumentally rational in this
economy. Finally, a **structural cross-check** compares intent-grounded labels against a
rule-based flag that fires whenever an agent invokes one of the three explicitly deceptive
actions; the disagreement cells quantify what intent-grounding adds over action-level
bookkeeping.

<!-- role: motivation + design, primary contribution -->
The fourth family addresses our central question, which a per-turn rate cannot answer: whether
deception is *sustained*. We group deceptive turns by (deceiver, target) ordered by turn and
segment each stream into **episodes**, maximal runs of deceptive stance toward one target,
split when the gap between consecutive deceptive turns exceeds a threshold. From the episode
set we derive **coherence**: the length of sustained campaigns, whether a campaign resumes
after interruption, whether it is abandoned once challenged, and whether coherence decays as
the horizon lengthens.

<!-- role: motivation — the correction that governs every coherence number we report -->
Coherence statistics cannot be read raw, and recognising this is part of the contribution.
The natural summary — the share of a deceiver's directed lies aimed at an already-deceived
victim — has a hard arithmetic floor: with at most nine rivals alive, an agent telling 86
directed lies cannot avoid repeating targets. Such a statistic measures lie volume divided by
pool size, not strategy. The same objection applies to the longest gap after which a deceiver
returns to a victim, since a frequent liar will revisit someone after a long silence by chance.

<!-- role: design — the null -->
We therefore evaluate every coherence statistic against a **permutation null**. For each
deceiver we hold its deceptive turn indices fixed and reassign each turn's *target* uniformly
among the agents alive on that turn, excluding itself, over 1,000 iterations. This preserves
how often the agent lied, when it lied, and how many rivals were available; only the choice of
victim is randomised, so what survives is target selectivity — which is what "campaign" means.
Agents excluded as deceivers for instrumentation reasons remain in the null's target pool,
since shrinking the pool would bias the test toward calling chance repetition selectivity. We
run one test per model per metric and control the false discovery rate across all of them with
Benjamini-Hochberg; uncorrected p-values are never reported as findings.

<!-- role: design — what was adopted, and what was rejected -->
Against that null we adopt three statistics: **repeat-target share**, **maximum contiguous
episode length**, and **maximum return gap**, each reported as observed-versus-chance. The
first and third are computed without segmentation and so do not depend on the episode gap
threshold; the sweep in the supplement shows the threshold is not load-bearing for the second
either. We rejected four candidates on evidence: *abandonment rate* is the algebraic inverse
of episode length and adds nothing; *narrative type-consistency* ranges only 0.63–0.69 across
high-volume models and conflates a coherent story with a model's fixed stylistic preference;
*episode density* ranges only 0.82–0.88 and does not discriminate; and a *coherence-versus-turn
slope* measures intensity rather than coherence and is reported separately as such.

## 4.5 Reliability protocol

<!-- role: motivation -->
Labels produced by a language model require their own validation, particularly when the default
judge shares a model family with an evaluated agent.

<!-- role: design -->
We therefore report three quantities. **Self-consistency** is the agreement of *K* independent
samples at temperature 0, which isolates provider nondeterminism. **Judge sensitivity** is the
agreement between the default judge and a judge from a different model family, which also
bounds self-preference bias. **Human agreement** is Cohen's κ between judge labels and human
annotations on a blind sample in which the annotator sees the full triple and ground truth but
neither the actor's identity nor the verdict.

<!-- role: design — the sampling subtlety that changes the headline number -->
Sampling design is not incidental here, because Cohen's κ is prevalence-sensitive. We draw two
samples. A **stratified** sample balanced 50/50 on the primary verdict maximises information
about the rare positive class, but its marginals are engineered, so its κ is not the population
value and it cannot test per-model ordering — round-robin balancing forces every model to
roughly 0.5 under the primary judge. A **prevalence-correct random** sample yields the
population κ and a valid ranking comparison. We report the random-sample κ as the headline and
the stratified κ alongside it, and we report agreement conditioned on the judge's own stated
confidence, because the two differ sharply in a way a single pooled number conceals.
