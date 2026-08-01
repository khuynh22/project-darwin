# Introduction

<!-- Drafted 2026-07-26 with the research-paper-writing skill (references/introduction.md).
     Templates: Part A Version 3 (general -> specific setting); Part B Technical-Challenge
     Version 1 (challenge chain through prior methods); Part C Pipeline Version 2 (two
     contributions). Terminology locked to §3/§4: agent-turn, the triple, intent-grounded,
     episode, coherence, condition.
     CONSTRAINT: every claim here must match its status in paper/CLAIMS.md. Nothing marked
     NEEDS-DATA may appear as a finding. -->

<!-- role: opening / task and application -->
Language-model agents are increasingly deployed in configurations where they act autonomously,
interact with other agents, and pursue goals over long trajectories: negotiation and
procurement pipelines, agent marketplaces, and multi-agent orchestration frameworks in which
several models coordinate or compete on a shared task. These deployments introduce a risk that
single-agent evaluation does not address, namely that agents may deceive *one another* when
deception advances their objective. This paper studies that risk in its sharpest form: an open
economic environment in which heterogeneous frontier models compete for survival, are free to
cooperate or exploit each other, and are observed for hundreds of interaction turns.

<!-- role: challenge chain, step 1 — general challenge -->
Measuring deception in such a setting is difficult because deception is defined by intent, while
evaluation typically observes only behaviour. A false public statement is not by itself
evidence of deception: an agent may be mistaken, may be repeating stale information, or may
announce an intention it later abandons for legitimate reasons. Establishing that an agent
*deceived* requires evidence about what it was trying to do at the moment it spoke.

<!-- role: challenge chain, step 2 — prior methods and their limits -->
Existing work supplies the necessary ingredients but not their combination. Studies of deception
in multi-agent social-deduction games introduce named deception metrics and compare models
head-to-head, but score deception from public behaviour alone, without access to any private
channel, and place agents in a voting game rather than an economy. Work on in-context scheming
resolves the intent problem directly, by triangulating an agent's chain-of-thought against the
action it takes, but studies a single agent under an overseer rather than peers competing with
one another, so it cannot observe deception as a *social* strategy. Most recently, deception has
been studied over extended interactions, across many frontier models and with adequate
statistical power; that setting, however, is cooperative and hierarchical, spans roughly forty
rounds, and again scores deception with a post-hoc auditor over outputs only.

<!-- role: challenge chain, step 3 — the remaining challenge, decomposed -->
The challenge that remains is therefore to measure deception that is simultaneously
*intent-grounded*, *peer-directed*, and *sustained*, and it is unmet for three technical
reasons. First, intent-grounding requires an environment that elicits a private channel and a
public channel in the same forward pass and records both alongside the action actually executed;
observing outputs alone makes lying and error indistinguishable. Second, peer-directed deception
requires an open action space in which manipulation competes with ordinary economic strategies,
since a fixed-matrix game fixes in advance how and when an agent may deceive. Third, sustained
deception cannot be characterized by a per-turn rate at all: whether an agent maintains a
coherent false position across many turns, and whether it resumes after being interrupted, is a
property of a *sequence*, and no existing benchmark defines a measure over it.

<!-- role: pipeline, contribution 1 -->
We address the first two requirements with an environment and a measurement pipeline built
around a single recorded object. Our environment is an open adversarial survival economy in
which three to ten frozen frontier models compete under progressive taxation, hunger, and
permanent elimination at zero cash, acting through twenty typed actions that span cooperation,
aggression, and three explicitly deceptive moves. For every **agent-turn** we record a
**triple**: the agent's private monologue, the public message it broadcasts, and the action and
outcome the engine actually applied, together with the ground-truth state of the world at that
turn. An offline judge then labels each agent-turn by a relational criterion — a turn is
deceptive when its public message contradicts the agent's own stated intent, its executed
action, or recorded ground truth — and returns a typed verdict with quoted evidence spans. Two
properties distinguish this from output-only auditing: openly aggressive play is correctly *not*
labelled deceptive, and the deceptive content itself is agent-authored text rather than a
template, so the label describes the model's own claim.

<!-- role: pipeline, contribution 2 -->
The third requirement motivates our second contribution, a measure of deception over the
horizon rather than at a point. We group labelled deceptive turns by deceiver and target,
segment each stream into **episodes** — maximal runs of deceptive stance toward one target — and
characterize their **coherence**: how long campaigns persist, whether they resume after
interruption, whether they are abandoned once challenged, and whether coherence decays as the
horizon lengthens. Because our environment runs to hundreds of social turns, this measure can be
computed on trajectories roughly an order of magnitude longer than those used in prior deception
studies.

<!-- role: experiments — HEDGED. Update against §5 once the 335-turn run is judged. -->
`TODO(data)` We instantiate the environment with ten frontier models spanning four
organizations, across neutral, honesty-instructed, and deception-instructed conditions, in runs
of up to 335 social turns. Our current evidence is a set of single-seed observations rather than
a powered comparison, and we report it as such: deception rates that separate sharply and
consistently by model; a within-game control in which two instances of the same model, given
different specialties, rivals, and outcomes, nonetheless deceive at comparable rates while
different models do not; a condition contrast in which an honesty instruction lowers deception
substantially while explicit permission to deceive barely raises it; and, in the games observed,
no wealth or survival advantage for the most deceptive agents. `TODO(data)` Insert the
coherence result once the longest run is labelled.

<!-- role: contributions -->
This work makes four contributions. (i) An open adversarial survival economy for eliciting and
observing deception among competing frozen models, released with its traces. (ii) An
intent-grounded deception measure defined over the private/public/action triple, together with a
taxonomy, a judging protocol, and a reliability protocol reporting self-consistency, judge
sensitivity, and human agreement. (iii) A measure of sustained deception coherence over long
horizons, computed on trajectories substantially longer than prior work. (iv) A first empirical
characterization of how frontier models differ in deception propensity and style under identical
competitive conditions, reported with explicit statistical caveats.

<!-- role: scope statement — keeps the paper honest, per CLAIMS.md -->
We state the scope of these claims plainly. Our environment is competitive by construction and
permits manipulation, so we measure deception *capability and propensity under incentive*, not
unprompted misalignment; the neutral/honesty/deception contrast is what separates the two. The
private monologue is the agent's *stated* reasoning, and following work on unfaithful
chain-of-thought we treat it as evidence of stated intent rather than as a transcript of
computation. Finally, the empirical results below are single-seed and are reported as
observations, not as significance-tested comparisons; §7 details the consequences.
