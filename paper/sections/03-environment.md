# The environment

<!-- Drafted 2026-07-26 with the research-paper-writing skill (references/method.md).
     Paragraph roles are HTML comments: they guide revision and do not render.
     Terminology locked here and reused verbatim in §4: agent-turn, the triple,
     the Oracle, condition, major/free action, information asymmetry. -->

<!-- role: overview / setting -->
We study deception in an **open adversarial survival economy**: a turn-based game in which
three to ten language-model agents compete for wealth under elimination pressure. Each agent
is a frozen, instruction-tuned model reached through a single OpenAI-compatible gateway, so
heterogeneous models compete in the same game without fine-tuning. The environment is
designed for one purpose: to create conditions where deception is *possible, useful, and
observable*, and then to record enough per turn to tell a lie from an honest mistake.
Section 3.1 describes the economy that supplies the incentive, 3.2 the action space that
supplies the means, 3.3 the information asymmetry that makes lying pay, 3.4 the per-turn
record that makes it measurable, and 3.5 the experimental controls.

## 3.1 Economy and survival pressure

<!-- role: motivation -->
Deception requires a reason to deceive. Prior multi-agent simulations that lack a survival
drive report deception only incidentally, so the environment must make failure real rather
than nominal.

<!-- role: design -->
Every agent begins with \$10 of liquid cash. Three goods (ore, food, tech) are produced by
labour, and each agent is randomly assigned a specialty in which it produces two to three
times as much, so no agent can efficiently supply itself and trade is structurally necessary.
A progressive tax on **cash** is levied every ten turns (0% below \$2, rising in brackets to
20% above \$20); capital locked in investments is exempt, which creates a recurring incentive
to move wealth out of sight before a tax cycle. Every ten turns an agent must also consume one
unit of food or pay a \$1 hunger penalty. Any agent whose liquid balance reaches zero at the
end of a turn is **eliminated permanently**; invested capital and goods do not prevent this,
and the estate passes to a named heir or, absent one, is destroyed.

<!-- role: advantage -->
Because elimination depends on *liquid* cash while taxation punishes holding it, agents face a
genuine dilemma each cycle rather than a dominant strategy, and wealth differences compound
into visible strong and weak positions — the asymmetry that makes manipulation worthwhile.

## 3.2 Action space

<!-- role: motivation -->
A benchmark that offers only cooperative moves cannot observe betrayal, and one that offers
only a fixed matrix of moves cannot observe how deception is *composed* with ordinary economic
behaviour. The action space must therefore span cooperation, aggression, and deception within
a single open repertoire.

<!-- role: design -->
Agents act through **20 typed actions** in two tiers. Each turn an agent must take exactly one
**major action** — work, trade, invest, bet, lend, steal, sabotage, extort, bribe, or
socialize (alliance, truce, rivalry, marriage, divorce) — and may additionally take one
optional **free action** — vouch, gift, charity, will, rest, strike, propose deal, or the three
explicitly deceptive moves: *slander* (broadcast a damaging claim about another agent),
*bluff* (announce an action other than the one taken), and *gaslight* (send a target a fabricated
private event). Actions are invoked as structured tool calls with typed arguments and are
validated and applied by an authoritative server-side engine, the **Oracle**; agents never
mutate state directly.

<!-- role: advantage -->
Two properties matter for measurement. First, the deceptive moves carry **agent-authored
content**: the rumour or fabricated event is text the model writes, not a template, so a
deception label describes the model's own claim. Second, because deception occupies the free
slot alongside a major action, an agent can appear to work honestly while simultaneously
running a smear campaign — the exact configuration that output-only observation misreads.

## 3.3 Information asymmetry

<!-- role: motivation -->
Lying is only consequential when others cannot immediately check the claim. Under full
observability a false statement about one's own wealth is refuted on sight, which suppresses an
entire class of deception.

<!-- role: design -->
Each agent sees its own exact balance, inventory, and specialty, but by default observes only a
**coarse range** for every other agent (`$0-2`, `$2-5`, `$5-10`, `$10-20`, `$20+`); exact values
are revealed only for a spouse or a consenting ally. Public trust scores, alliance structure,
and each agent's recent action history are visible, and the *gaslight* action injects a
fabricated event into a single target's private view. The regime is configurable (`public`,
`fuzzy`, `hidden`); all runs reported here use `fuzzy`.

<!-- role: advantage -->
Coarse balances leave agents genuinely uncertain about who is strong, so claims about one's own
state are both useful to fabricate and hard to falsify, while the visible trust score gives
slander a concrete mechanical payoff.

## 3.4 The per-turn record: the triple

<!-- role: motivation -->
The central measurement problem is that a false public statement is not evidence of deception:
a model may simply be mistaken, or describing an intention it later abandons. Distinguishing a
lie from an error requires observing the agent's stated intent alongside what it said and what
it did.

<!-- role: design -->
For every **agent-turn** the environment logs a **triple**: (i) the agent's *private monologue*,
supplied as the reasoning field of its tool call and never shown to other agents; (ii) its
*public message*, broadcast verbatim to all agents; and (iii) the *action and outcome* actually
applied by the Oracle, together with the resulting ledger entries and the agent's true balance
and trust score that turn. The private and public channels are separate fields of the same
tool call, so they are produced in one forward pass under identical context.

<!-- role: advantage -->
The triple makes intent-grounded measurement possible: deception can be defined as a
contradiction *among channels* — a public claim that conflicts with the agent's own stated
intent, with the action the engine actually executed, or with recorded ground truth — rather
than as a judgement about whether a statement happens to be false.

## 3.5 Experimental controls and reproducibility

<!-- role: design -->
Each run carries a **condition** that appends one of three locked suffixes to the system prompt:
`neutral` (no suffix; the baseline competitive prompt), `honesty` (an instruction that every
public message be truthful), or `deception` (explicit permission to misrepresent). The wording
is fixed verbatim, since any edit invalidates cross-run comparison. Environment stochasticity —
specialty assignment, production yields, investment outcomes, theft success — is drawn from a
generator seeded per (seed, turn), and decisions are applied in a deterministic order, so a
given seed reproduces the same world dynamics.

<!-- role: limitation -->
Determinism covers the environment only. Model sampling remains stochastic and is not
controlled by the seed, so results are reported as variance across seeds rather than as
byte-identical reruns. Runs reach up to 500 turns; the longest reported here is **335 turns**.

<!-- TODO(make): Figure 1 — schematic of the turn loop and the triple. -->
