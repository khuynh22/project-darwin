# Project Darwin — Research Landscape & Positioning (v3, two verified passes)

**Date:** 2026-06-06 (v3 update 2026-06-07)
**Status:** Instrument verified from source code. Literature verified across **two adversarial
deep-research passes** (pass 1: deception/social-sim/model-eval; pass 2: long-horizon, game-theoretic,
venues). Combined: 55 sources fetched, 50 claims fact-checked (2-of-3 vote), 45 confirmed / 5 refuted.
**Goal:** Decide whether and how to publish a research paper using Project Darwin as the instrument.

> **Verification legend:** `✅ VERIFIED` = ≥1 primary source, vote ≥2-1 · `🟡 LEAD` = source fetched,
> claim not synthesized · `🔴 RECALL-ONLY` = model memory, not surfaced · `❌ REFUTED` = killed over-claim.

---

## 1. What Project Darwin is (verified from code)
Multi-agent LLM **economic-survival simulation** as a behavioral-elicitation instrument.
- **Adversarial prompt** (`agents/base.py`): win by ≥90% wealth or last alive; be manipulative; betray; exploit.
- **20-action space** (`oracle/schemas.py`,`actions.py`): cooperation (trade, alliance, marriage→pools
  balances, lend, gift, charity, vouch), aggression (steal, sabotage, extort), risk (bet), economy
  (work, invest, strike), **deception** (bluff, gaslight, slander, + a `public_message` channel where "lies welcome").
- **Survival pressure:** $10 start, progressive tax/10 turns, food/hunger, bankruptcy at $0, inheritance/wills. Up to **500 turns**.
- **Info asymmetry as a manipulation:** `public`/`fuzzy`/`hidden` balances + gaslight injection.
- **Cross-model + MIXED-model head-to-head** via OpenRouter (frozen-weight inference; `openai_agent.py`, no fine-tuning).
- **★ The logged TRIPLE** (`models/ledger.py` → JSONL): per agent-turn = **private monologue** + **public_message** + **action+outcome**. The core asset (intent-grounded deception measurement).
- **Engineering status (updated 2026-06-07):** ✅ **fixed-seed reproducibility DONE** (per-`(seed,turn)`
  environment RNG + seeded stub agents, deterministic apply/tax/bankruptcy/ledger order, seed recorded +
  surfaced + `--seed` CLI flag; verified same-seed→byte-identical via tests + cross-process CLI check).
  *Scope:* fixes the **environment**; LLM sampling stays stochastic, so report **variance over seeds**, not
  "byte-identical runs." ✅ **Structural metrics/analysis layer DONE** (`app/metrics.py` +
  `scripts/compute_metrics.py` → JSON + per-turn CSV: Gini-over-time, action taxonomy, deception rate,
  betrayal timing, bluff-mismatch, per-model rollup; new `TurnSnapshot` table for longitudinal data;
  private/public/action **triple now complete in the JSONL export**). ⏳ Remaining (**Phase 2**): the
  **LLM-judge intent-grounded deception** metric (needs API + human-validated labels).

---

## 2. The headline result (✅ VERIFIED across both passes)
> **No surveyed system combines: open adversarial economic survival + mixed-model tournaments +
> ~500-turn horizon + the private/public/action TRIPLE.** Each axis exists somewhere; the *integration*,
> anchored on the intent-grounded triple, is un-scooped on current evidence.
>
> ⚠️ Absence-of-prior-art is not provable from a finite search, and this space moves fast (closest
> competitors are Jan–Apr 2026). **Re-sweep immediately before submitting.**

---

## 3. Related-work map (verified) + where Darwin sits

### Framing 1 — AI safety / deception (strongest fit; partly occupied)
- **✅ The Traitors (arXiv:2505.12923, UvA).** Nearest on the *deception-metrics* axis: 10-agent social
  deduction, named metrics suite (deception success, trust dynamics), **cross-model** (GPT-4o 93% vs
  DeepSeek 33% traitor-survival). **But:** no private-reasoning channel; **voting** game (no economy);
  **homogeneous** populations; **n=10**, self-described underpowered ("precludes definitive significance testing").
- **✅ Apollo in-context scheming (arXiv:2412.04984).** Method anchor: proves *intentional* deception via
  **CoT-vs-action** triangulation. **But:** single-agent vs **overseer**, not multi-agent peer economy.
- **✅ Park et al. survey (arXiv:2308.14752, Patterns 2024).** Functional deception definition; flags
  "tools to detect AI deception" as an **open** priority. Darwin's monologue-check *exceeds* its outcome-only bar.
- **✅ CONSCIENTIA (arXiv:2604.09746, 2026).** Multi-agent NYC navigation Red/Blue; **but** it's RL/KTO
  policy-**learning** (trains agents) — Darwin is frozen-weight inference — and has no economy/triple.

### Framing 2 — Emergent multi-agent social simulation
- **✅ Project Sid (arXiv:2411.00114).** Emergent roles/rules/culture; **has an economy + ~20% taxation**,
  so Darwin is NOT novel for "having an economy." Sid's own gap: agents "lack robust drives such as
  **survival**"; deception only incidental. Darwin's edge = survival-linked elimination + deception measurement.
- **✅ Concordia (arXiv:2312.03664, DeepMind).** GABM library, "Game Master" ≈ Darwin's Oracle, but
  free-form NL vs Darwin's fixed 20-action schema; audit trail is for explainability, not deception metrics.
- **✅ Sugarscape LLM (arXiv:2508.12920).** Survival/elimination-at-zero + **cross-model aggression**
  (GPT-4o 83% attack vs Gemini ~50%). **But:** ALife energy-grid (no money/market/tax/trade), no triple,
  no encouraged lying, emergence *without* adversarial prompt. Overlaps only survival mechanics.
- **✅ Survival Games (arXiv:2505.17937, ICML'25).** 2 humans + 1 LLM (not 3–10 cross-model); deception
  via adapted MACHIAVELLI, not a triple.
- **🔴 RECALL-ONLY:** Generative Agents (Smallville), AI Town — canonical, not re-verified here.

### Framing 3 — Game-theoretic / behavioral-economic (✅ NOW VERIFIED)
- **✅ GTBench (arXiv:2402.12348, NeurIPS 2024).** Establishes **cross-model LLM strategic tournaments**
  (LLM-vs-LLM + LLM-vs-MCTS) — but over **10 FIXED-form games** (Kuhn Poker, Liar's Dice, Iterated PD,
  Blind Auction, Negotiation…), all with well-defined action spaces and predetermined endpoints.
- **✅ EconAgent (ACL 2024, aclanthology 2024.acl-long.829)** + a Nature Human Behaviour LLM
  behavioral-economics study (s41562-025-02172-y) — economic/agent-econ lineage.
- **✅ KEY NEGATIVE RESULT:** *No verified source runs an **open-ended (non-fixed-matrix)** multi-agent
  economic-survival game with LLMs measuring **cross-model cooperation/betrayal**.* → Darwin's open-world
  20-action survival economy with encouraged deception is **differentiated from all fixed-matrix tournaments.**

### Framing 5 — Long-horizon / long-trajectory (✅ NOW VERIFIED — your top priority)
- **✅ The whole long-horizon field is SINGLE-agent task-completion**, and measures horizon in
  **tokens/tool-calls, not social turns**: METR "time horizon" (metr.org, ~7-month doubling; single-agent
  HCAST/SWE-Bench), **UltraHorizon (arXiv:2509.21766)** (rule-discovery, 200k+ tokens/400+ tool-calls),
  **OdysseyBench (arXiv:2508.09124)** (office workflows). → **Darwin is differentiated on the
  multi-agent-SOCIAL-turn axis** — a clean second wedge alongside the triple.
- **✅ Goal/persona drift is already an instrumented phenomenon — cite, don't claim:**
  - **Apollo goal-drift eval (arXiv:2505.02709, AIES 2025):** metrics **GD_actions / GD_inaction**, 20 seeds;
    GPT-4o-mini drifts after **16 steps**, scaffolded Claude 3.5 Sonnet holds >100k tokens — **but single-agent**
    stock-trading ("Apex Capital"), not multi-agent social/survival.
  - **"Agent drift" / Agent Stability Index (arXiv:2601.04170, Jan 2026):** names a 12-dimension drift metric
    — **but** single-author, synthetic-data-only, non-peer-reviewed, no deception/adversarial/survival.
    Scooping is **terminology-only; differentiation bar is LOW** (cite-and-distinguish).
- **✅✅ #1 SCOOPING RISK — LH-Deception (arXiv:2510.03999, ICLR 2026).** Explicitly studies **deception over
  long-horizon** interactions, **11 frontier models, n=20**. **But it is differentiated from Darwin on four
  axes:** (1) **cooperative**-hierarchical (one performer → one supervisor), not adversarial peer economy;
  (2) **~42 rounds** (14 tasks × 3), not ~500 turns; (3) deception scored by a **post-hoc auditor over
  OUTPUTS only — no private-reasoning channel**, so **not intent-grounded**; (4) no economy/survival.
- **✅ OPEN METRIC NOBODY OWNS (the sharpest opportunity):** the verifier could not locate any benchmark
  measuring **"deception/strategy COHERENCE sustained over hundreds of social turns"** (vs deception rate at
  a point). LH-Deception=42 rounds output-only; Apollo=single-agent drift. **This fuses your two priorities
  (long-horizon × deception) into a metric Darwin could define and own.**

---

## 4. Genuine novelty vs already-done (post two passes)
**Already occupied — do NOT claim novel:** economic-survival (Sid/Sugarscape/Survival Games) · cross-model
deception tournament (The Traitors) · cross-model strategic tournament (GTBench) · CoT-vs-action deception
(Apollo) · survival→model-distinct behavior (Sugarscape) · goal-drift metrics (Apollo, ASI) · deception-over-
long-horizon framing (LH-Deception).

**Robust, defensible novelty (the integration + two ownable wedges):**
1. **The intent-grounded triple** in an open adversarial economy with mixed-model tournaments (✅ un-scooped).
2. **Sustained deception/strategy coherence over ~500 social turns** — an open metric (✅ not located in prior art).

---

## 5. Strongest publishable contribution (recommendation)
**Lead with a fusion of your two strongest framings: "Measuring sustained, intent-grounded deception in an
open multi-agent survival economy over long horizons,"** positioned precisely against the two nearest works:
- **vs LH-Deception (ICLR'26):** adversarial (not cooperative), open economy (not 14 tasks), **~500 turns
  (not 42 rounds)**, **intent-grounded triple** (not output-only auditor), **mixed-model** (not single-model runs).
- **vs The Traitors:** intent-grounded + open economy + mixed-model + adequately powered (beat n=10).
- **vs Apollo:** multi-agent peer + incentivized + the long-horizon *coherence* metric (not single-agent drift).

**Confront the two reviewer-killers up front:**
1. **Instructed deception ≠ misalignment.** You measure **capability + propensity**. Run **neutral /
   honesty-instructed / deception-instructed** conditions; the signal is the *difference* + cross-model
   variation under identical instructions (Sugarscape's emergent-vs-instructed design is the precedent).
2. **Monologue = *stated* reasoning, not true cognition** (unfaithful-CoT). Frame as stated-private vs
   stated-public vs action; use Apollo's intentionality argument as the template.

---

## 6. Metrics extractable from the trace (+ verified prior use)
- **Deception rate / success, trust, betrayal, survival** — ✅ prior use (The Traitors); frame as
  replication+extension, key to the **economy** (wealth/Gini/extortion) to avoid overlap.
- **Intent-grounded deception** (monologue vs public_message vs action mismatch) — novel form; needs
  human-validated labels.
- **Sustained-deception-coherence over horizon** — ✅ **not located in prior art → candidate to own.**
- **Stated-vs-revealed-preference gap, Gini-over-time, mixed-model Elo** — standard elsewhere; novelty as
  *deception measures* unconfirmed.

---

## 7. Venues + methodology bar (✅ bar VERIFIED via accepted comparables)
**Concrete evidence bar (from accepted/comparable papers):**
- **n=10 FAILS** (The Traitors self-reported underpowered). **n=20 CLEARED ICLR 2026** (LH-Deception:
  20 trials/model, **11 frontier models**, mean±std.err).
- → Darwin should run **≥20 seeded runs/condition**, report variance/SE, broad multi-model coverage, and
  **human-validate deception labels**. **Note:** Darwin's mixed-model factorial (model-mix × seed) multiplies
  cell count vs homogeneous designs — do a **power analysis** for the actual design.
- Close the gaps first: ✅ **fixed RNG seed (done)** + ✅ **structural metrics layer (done)**; ⏳ LLM-judge
  deception metric remains (Phase 2, needs human-validated labels).

**Venue targets (fit reasoning ✅; exact requirements 🟡 — see caveat):**
- **NeurIPS Datasets & Benchmarks** (note: NeurIPS 2026 has a **new "Evaluations & Datasets" track**,
  blog.neurips.cc/2026/03/23) — best fit for "environment + trace dataset + metrics + multi-model." Expect
  mandatory **datasheet/dataset card + reproducibility**.
- **AIES** (aies-conference.com/2026) — strong fit for the deception/safety framing (where Apollo's
  goal-drift landed).
- **ICLR** — proven viable by LH-Deception.
- **AAMAS** (cyprusconferences.org/aamas2026) — multi-agent framing. **ACL/EMNLP** — linguistic deception.
- **Cooperative-AI / multi-agent / safety workshops** — best **first** flag-planting home.
- 🟡 **CAVEAT:** the *official* requirement pages (NeurIPS D&B guidelines, AIES CFP, arXiv:2411.00640,
  2507.02825) were fetched but their specific mandates (datasheets, page limits, significance/human-validation
  rules) were **inferred from comparable accepted papers, not read off the 2026 calls.** Fetch those before
  building a submission checklist.

---

## 8. ❌ Refuted claims — do NOT put in the paper
1. "The Traitors lacking an economy proves Darwin's economic framing is novel." (Sid/Sugarscape/Survival Games have economies.)
2. "CONSCIENTIA finds limited strategic behavior, comparable to Darwin."
3. "Project Sid (10→1000+ agents) is the closest prior art on the agent-count axis."
4. "Survival Games is a close adversarial multi-LLM survival instrument." (It's 2 humans + 1 LLM.)
5. "OdysseyBench's horizon is only 3–15 turns." (Killed; don't use it to argue others' horizons are short.)

---

## 9. Verified source list (both passes)
✅ Claim-verified: 2505.12923 (The Traitors) · 2412.04984 (Apollo scheming) · 2308.14752 (Park survey) ·
2604.09746 (CONSCIENTIA) · 2411.00114 (Project Sid) · 2312.03664 (Concordia) · 2508.12920 (Sugarscape) ·
2505.17937 (Survival Games) · 2107.06857+blog (Melting Pot) · **2402.12348 (GTBench, NeurIPS'24)** ·
2024.acl-long.829 (EconAgent) · s41562-025-02172-y (Nature HB) · **metr.org/2025-03-19 (METR)** ·
**2509.21766 (UltraHorizon)** · **2508.09124 (OdysseyBench)** · **2505.02709 (Apollo goal-drift, AIES'25)** ·
**2601.04170 (Agent Stability Index)** · **2510.03999 (LH-Deception, ICLR'26)**.
🟡 Fetched, requirements not verified: neurips.cc 2026 D&B guidelines · blog.neurips.cc 2026 Eval&Datasets ·
aies-conference.com 2026 CFP · cyprusconferences.org/aamas2026 · 2411.00640 · 2507.02825.

---

## 10. Next steps
1. **Engineering prerequisites (do regardless of framing):** ✅ **fixed RNG seed — DONE** (reproducible
   environment from a recorded per-session seed; LLM sampling stays stochastic by design — report variance
   over seeds). ✅ **Structural metrics/analysis layer — DONE** (`app/metrics.py` + `scripts/compute_metrics.py`:
   Gini-over-time, action taxonomy, deception rate, betrayal timing, per-model rollup, per-turn CSV).
   ⏳ Still to add (Phase 2): the **LLM-judge intent-grounded deception** + **deception-coherence-over-horizon**
   metric (needs API + human-validated labels).
2. **Power analysis** for the mixed-model × seed factorial → set runs/condition (target ≥20).
3. **Fetch the official 2026 venue calls** (NeurIPS D&B / AIES) for a submission checklist.
4. **Draft a workshop paper** (Cooperative-AI / safety) positioned explicitly vs **LH-Deception**, **The
   Traitors**, **Apollo** — leading with the two ownable wedges (intent-grounded triple + long-horizon
   deception coherence).
5. **Fresh prior-art re-sweep immediately before submission** (fast-moving area).
