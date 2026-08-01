# Limitations

*(Drafted first, deliberately: these caveats constrain every claim elsewhere. Source: `CLAIMS.md`.)*

**Statistical power.** Our runs are single games per condition (n=1/cell). We report
*directions and existence*, not significance; no confidence intervals or hypothesis tests
are claimed. The bar for cross-model significance in comparable work is ≥20 seeded runs per
condition; reaching it is future work. `TODO(data)` if seed replication lands.

**Instructed vs. emergent.** The "neutral" condition is not instruction-free: it is an
adversarial survival prompt that *permits* manipulation without mandating it. We therefore
measure **capability and propensity under competitive incentive**, not unprompted
misalignment. The neutral↔honesty↔deception contrast is what separates propensity from
obedience, and even there the honesty effect is modest and concentrated in one model.

**Stated reasoning ≠ cognition.** The private monologue is the agent's *stated* reasoning.
Consistent with the unfaithful-CoT literature, we never claim access to what a model
"really thought"; every verdict is a contradiction among *stated* private intent, *claimed*
public message, and *actual* action + ground truth.

**Judge validity.** Labels come from an LLM judge whose reliability we report but have not
yet fully established: self-consistency (K>1), judge-model sensitivity, and human
agreement (Cohen's κ) are pending. Notably the default judge shares a family with one
evaluated model, so self-preference bias is possible and currently unmeasured.

**Environment confounds.** Random per-agent specialties and stochastic yields materially
affect outcomes. Our clearest illustration: two instances of the same model finished
$173.17 and $1.20 while deceiving at similar rates — model predicts *behavior*, but luck
substantially drives *outcome*. Wealth/survival-linked claims inherit this noise.

**Data-collection caveats.** In the ten-model run, one model (Kimi) failed to emit valid
tool calls on 56% of its turns and is excluded as an instrumentation artifact rather than
a behavioral result. That run was judged from the exported trace (ground truth via the
recorded outcome string) rather than full database state.
