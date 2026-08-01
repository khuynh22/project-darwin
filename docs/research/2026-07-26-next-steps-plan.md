# Next-steps plan — from data to submittable paper

**Date:** 2026-07-26
**Context:** Instrument built and validated; five runs collected (see `paper/data/README.md`);
paper scaffold at `paper/`. This plan sequences what remains.
**Governing rule:** every phase must move a row in `paper/CLAIMS.md` from `NEEDS-DATA` →
`DIRECTIONAL` → `SUPPORTED`. If a phase doesn't change a claim's status, it isn't on the
critical path.

## Current blocker (clears everything else)

**The OpenRouter key's spend cap is at $0 headroom** (account balance is fine, ~$79).
Nothing that calls a model can run until the cap is raised/removed at
openrouter.ai/settings/keys. **Fix this first** — Phases 0–4 all depend on it.

---

## Phase 0 — Judge the 335-turn run *(immediate, ~$65, ~15 min)*

Run the ready adapter over the 10-model / 335-turn export.

```bash
OPENROUTER_API_KEY=$KEY python research/leaderboard_335t_20260726/judge_export.py --provider openrouter
```

- 1,601 judgeable rows (Kimi + skip/fallback turns excluded); resumable; Opus v2 judge.
- **Unlocks:** R1 (9-model leaderboard) and the raw material for R4 (coherence).
- **Claims moved:** H1 → stronger `DIRECTIONAL`; H3 becomes computable.
- **Exit criterion:** `verdicts_335t.jsonl` complete; deception rate per model computed.

## Phase 1 — Define + implement the coherence metric *(the headline wedge)*

The Phase-2 design deliberately deferred this formula until real verdicts existed. They now will.

1. Reconstruct **episodes**: group deceptive turns by `(deceiver → target)`, segment with a
   max-gap rule.
2. Compute candidates on the 335-turn data: max/mean episode length; **resumption-after-gap**
   rate; abandonment rate; narrative self-consistency within an episode;
   **coherence-vs-turn slope** (does it decay over a long horizon?).
3. Pick the operationalization with actual signal, implement as `coherence_metrics()`, and
   freeze it. Document why the others were rejected.
- **Claims moved:** H3 `NEEDS-DATA` → `DIRECTIONAL`; N3's metric becomes real.
- **Why it matters:** this is the contribution no prior work owns. 335 turns is ~8× the
  nearest comparator's horizon.
- **Exit criterion:** a frozen formula + `fig_coherence_335t.png`.

## Phase 2 — Judge reliability *(credibility gate, ~$25)*

Reviewers will not accept LLM-judge labels without this.
1. **Self-consistency:** K=3 on a stratified sample.
2. **Judge sensitivity:** re-judge the same sample with a *different* judge family — this also
   addresses the Opus-judges-Opus self-preference risk.
3. **Human validation:** stratified blind sample → you label → **Cohen's κ**.
- **Claims moved:** M4 `NEEDS-DATA` → `SUPPORTED`.
- **Exit criterion:** κ and self-consistency numbers ready to state in §4.

## Phase 3 — Seed replication *(promotes the core claim, ~$90)*

Neutral condition, fixed roster, **5 seeds × ~30 turns**, judged.
- Question: does the model ordering (Opus/Gemini ≫ GPT-5/Grok) hold every seed?
- **Claims moved:** H1 `DIRECTIONAL` → `SUPPORTED` *with variance* (this is the single
  biggest credibility upgrade available).
- **Exit criterion:** per-model rate with spread across seeds; ordering stable or not.
- *If the ordering scrambles, that is itself the finding — and better learned now.*

## Phase 4 — Condition contrast at scale *(~$120)*

3 conditions × 5 seeds, blank personas.
- **Claims moved:** H2 `DIRECTIONAL` → `SUPPORTED`; also resolves H1b (persona vs model).
- **Exit criterion:** the causal table with variance — the emergence result.

## Phase 5 — Write *(no API cost)*

Use the `research-paper-writing` skill; drafting order from `paper/OUTLINE.md`:
§7 Limitations → §3 Environment → §4 Method → §2 Related Work → §1 Intro → **gate** → §5
Results → §6 Discussion → §0 Abstract.
- Per section: load only that section's `references/*.md`, draft, reverse-outline, produce a
  claim-evidence map, reconcile against `CLAIMS.md`.
- Then run `references/paper-review.md` adversarial self-review across the five dimensions.
- **Exit criterion:** full draft with zero `NEEDS-DATA` claims stated as findings.

## Phase 6 — Pre-submission

1. **Re-sweep prior art** — the positioning doc is from 2026-06-06 and the closest works are
   recent. Confirm nothing now occupies the intersection (N1/N2/N3).
2. Fetch the **actual venue CFP** (page limits, datasheet requirements) — currently inferred
   from comparable papers, not read off the calls.
3. Dataset card / datasheet if targeting NeurIPS D&B.
4. Final adversarial review; verify every figure caption carries its caveat.

---

## Sequencing

**Critical path to a workshop paper:** Phase 0 → 1 → 2 → 5. That yields the coherence wedge
plus a validated judge — a defensible flag-planting paper with honest single-seed caveats.

**For a full venue (NeurIPS D&B / AIES):** add Phases 3 and 4 to convert H1 and H2 from
directional to supported. Total remaining API cost ≈ **$300**.

**Recommended next action:** raise the key cap, then run Phase 0.

## Risks

| risk | mitigation |
|---|---|
| Coherence metric shows no signal | Fall back to episode-length descriptives; the leaderboard + emergence results still carry a workshop paper. |
| Seed replication scrambles the model ordering | Report it honestly — a negative result on H1 still supports the *instrument* contribution. |
| Judge-vs-human κ is low | Revise the judge prompt (bump version), re-judge; do not silently keep weak labels. |
| Scooped before submission | Phase 6 re-sweep; prefer the earlier workshop deadline for flag-planting. |
| Budget/key limits stall a run mid-flight | Guard on **account credits** (`/api/v1/credits`), not the key cap; all runners already resume. |
