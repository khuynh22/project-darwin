# Prior-art re-sweep — 2026-08-01

**Why:** the positioning doc is from 2026-06-06 and Phase 6 requires confirming that nothing
now occupies the N1/N2/N3 intersection before submission. Two months of arXiv have landed
since. **One paper materially narrows N1.**

Scope: searched for multi-agent LLM deception benchmarks, long-horizon multi-agent autonomy,
and intent-grounded / CoT-vs-output deception measurement. Four candidates were read in full
against the claim ledger.

---

## The one that matters — Emergence World (arXiv 2606.08367, Jun 2026)

*"Emergence World: A Platform for Evaluating Long-Horizon Multi-Agent Autonomy"*

This is the closest work that exists and it **was not in the 2026-06-06 sweep**. It overlaps
Darwin on three of the four axes N1 claimed as a combination:

| axis | Emergence World | Darwin |
|---|---|---|
| economic / survival, competing agents | ✔ 10 agents, energy + compute-credit economy, 40+ locations, governance votes | ✔ 3–10 agents, goods economy, 20 actions |
| **mixed-model in one run** | ✔ heterogeneous world: Claude + Grok + Gemini + GPT-5-mini, 2–3 agents/vendor | ✔ 10 models in one game |
| long horizon | ✔ 15 continuous simulated days | ✔ 335 social turns |
| **intent-grounded triple** | ✖ — LLM classifier (Gemini 2.5 Flash) over speech/messages/diary, **validated against the ledger**. Explicitly *"database confirmation rather than intent modeling."* | ✔ stated-private intent × public claim × actual action |
| **quantified deception coherence** | ✖ — reports temporal "bursts, plateaus, accumulation" and cumulative counts. Explicitly **no** analysis of whether an agent sustained a strategy across interactions or **resumed after interruption**. | ✔ this is the contribution |

**Verdict.** N1 as previously worded — "no prior work combines open adversarial economic
survival + mixed-model + long horizon + the intent-grounded triple" — is **no longer safe as
stated**. Emergence World owns the first three. What remains unoccupied, and is now the
*only* defensible novelty framing:

> the **intent-grounded triple** as the labelling substrate, and a **quantified coherence
> metric** over a long horizon.

**Action taken:** N1 downgraded and re-scoped in `paper/CLAIMS.md`; N3 is now the load-bearing
novelty claim. Emergence World must be cited in §2 as the nearest neighbour and explicitly
distinguished on measurement — not on setting, where we would lose.

**Framing note.** Their horizon is wall-clock/simulated-days; ours is *social turns between
peers*. These are not the same quantity, and we must not imply ours is longer without stating
the unit. Their per-agent turn count is not reported, so no horizon comparison is defensible.

---

## The other three — no threat, but cite

**CONSCIENTIA (arXiv 2604.09746, Apr 2026)** — emergent deception + trust in a 250-agent NYC
navigation sim. **Single model family** (Qwen3-4B/14B), not an economy, and deception is
measured by *action divergence* ("did the blue agent move to the suggested billboard"), never
from private reasoning. Documents multi-turn manipulation (repeated steering → 93.9%
susceptibility; delayed compromise → 100%) but **not** resumption after gaps. Cite as the
closest *emergence* result; distinguish on mixed-model + intent-grounding.

**Scheming Ability in LLM-to-LLM Strategic Interactions (arXiv 2510.12826)** — 4 models, but
**asymmetric dyads** (sender/receiver, evaluator/evaluatee), not competing peers in one arena;
no fixed long horizon; strategies counted by a Claude-Sonnet-4 labeller. Authors concede
multi-turn coherence "isn't analyzed systematically." **N2 (competing peers) survives.**

**Coercion and Deception in AI-to-AI Management (arXiv 2607.15434, Jul 2026)** — 6 models but
each tested **separately** against a fixed Haiku subordinate; asymmetric manager/worker; ≤12
turns; coercion is **self-reported** by the model against a 9-rung rubric with "no LLM judge in
the scoring path," fabrication adjudicated by two judges over public messages only. Each
conversation independent — no campaigns. No overlap with N3.

---

## Net effect on the claim ledger

| claim | before | after |
|---|---|---|
| N1 | SUPPORTED (4-way combination) | **re-scoped** — the setting combination is no longer novel; only the *measurement* combination is |
| N2 | SUPPORTED | **holds** — every peer-competition candidate is asymmetric dyads or single-model |
| N3 | SUPPORTED as a gap | **holds, and strengthened** — the nearest neighbour explicitly declines to measure it |

**Consequence for the paper:** the wedge is now unambiguously *measurement*, not *environment*.
Lead §1 and §2 with the triple and the coherence metric. Do not lead with "we built a
long-horizon mixed-model economy" — Emergence World did that, at scale, first.

## Re-sweep hygiene

Re-run before submission; the field is moving at roughly one near-neighbour per two months.
Queries used: multi-agent LLM deception benchmark long-horizon emergent 2026; intent-grounded /
CoT-vs-public-message deception measurement; long-horizon multi-agent autonomy platform.
