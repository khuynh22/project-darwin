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

**Unequal exposure and survivorship.** Agents in the ten-model run were eliminated at very
different times — from 36 turns to the full 335, a ~9× spread — so the models are not
observed under comparable conditions. Deception rates are exposure-normalised, but a
short-lived agent is scored only on early turns, when the economy is uncrowded and there is
little accumulated trust to exploit. The long-horizon coherence results are more exposed
still: only agents that survived can sustain a campaign, so **coherence is conditioned on
survival, and survival is itself strategy-dependent**. We therefore report coherence for
survivors descriptively and do not treat a low coherence score for an early-eliminated model
as evidence that it *cannot* sustain a campaign.

**Environment novelty.** We do not claim the environment as the contribution. Concurrent
platform work fields a mixed-vendor agent population in a scarcity economy over a long
horizon; our claims are confined to the *measurement* — intent-grounded labelling from the
triple, and the coherence metric — and §2 states this explicitly. A reader looking for a
novel simulator should look elsewhere.

**Data-collection caveats.** In the ten-model run, one model (Kimi) failed to emit valid
tool calls on 56% of its turns and is excluded **as a deceiver** for that reason — an
instrumentation artifact, not a behavioral result. It remains present in the world and can
still be *targeted*, so it appears on the target axis of our campaign figure while
contributing no deception rate of its own. That run was judged from the exported trace
(ground truth via the recorded outcome string) rather than full database state.
