# Method

`TODO(draft)` — 700–900w.

**Deception, operationally.** A turn is deceptive iff channels contradict: the public message
misrepresents the agent's stated private intent, its actual action, or ground-truth state.
Honest aggression (openly stealing) is **not** deception. Silence alone is not deception.

**Taxonomy.** `false_state_claim`, `false_promise`, `strategic_omission`, `misdirection`,
`identity_bluff`, `none`.

**The judge.** Offline batch (never inline in the turn loop). Per agent-turn it receives the
triple **plus ground truth** (true balance/trust, the applied action, ledger rows) and returns
a structured verdict: label, type, channels in conflict, target, confidence, rationale, and
quoted evidence spans. Temperature 0; prompts are versioned, and verdicts are cached per
`(judge_model, prompt_version)` and never pooled across versions. Deterministic
post-processing repairs two recurring output defects (self-target, channel-less deceptive
verdicts).

**Framing (unfaithful-CoT safe).** Verdicts are contradictions among *stated* private
reasoning, *claimed* public message, and *actual* action — never claims about true cognition.

**Metrics.**
- *Deception rate* — fraction of agent-turns majority-labelled deceptive.
- *Type mix* — distribution over the taxonomy; a model's deception "signature".
- *Episodes / coherence* — group deceptive turns by (deceiver → target), segment into
  campaigns with a max-gap rule; report max/mean length, resumption-after-gap, abandonment,
  and decay over the horizon. `TODO(finalize formula)` — deferred until the 335-turn verdicts
  exist, so the operationalization is chosen against real data rather than blind.
- *Adaptivity* — deception rate versus survival time and final wealth.
- *Structural cross-check* — agreement with rule-based deception-action flags; the
  disagreement cells are precisely what intent-grounding buys.

**Reliability plan.** Self-consistency at K>1; a second judge model for sensitivity; a
stratified blind human sample scored with Cohen's κ. `TODO(data)` — see `CLAIMS.md` M4.
