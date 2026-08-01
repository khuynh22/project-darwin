# Results

**BLOCKED** — needs the 335-turn judging plus the coherence metric. Skeleton only; do not
draft prose until numbers are in. Every claim cites its `CLAIMS.md` row and carries its caveat.

**R1 — Cross-model deception leaderboard (H1).** `TODO(data)` — 9-model rate ranking from the
335-turn run. Corroborate with the earlier runs where the ordering held (Opus/Gemini ≫
GPT-5/Grok). *Directional; single seed; no significance language.*

**R2 — Model, not seat (H1a).** Two instances of each model land in the same band despite
different specialties, rivals, and fates (Opus 39%/45%; Grok 0%/6%). Figure:
`fig_model_not_seat.png`. *Strongest single result — a within-game control, but one game.*

**R3 — Emergence, not instruction (H2).** The honesty instruction lowers deception
(24%→14%); explicit permission barely moves it (→25%), implying the competitive baseline
already sits near ceiling. Instruction also shifts the *kind* of deception. Figures:
`fig_condition_contrast.png`, `fig_type_mix_condition.png`. *n=1 per cell.*

**R4 — Sustained coherence over the horizon (H3) — headline.** `TODO(data)` — episode
lengths, resumption after interruption, decay across 335 turns. Preview: a 10-turn targeted
campaign with a gap and resumption (`fig_campaigns.png`). *The wedge no prior work owns —
roughly 8× the horizon of the nearest comparator.*

**R5 — Deception did not pay (H4).** The apex winner deceived at 13% versus a 26% field mean;
the heaviest deceivers finished near broke; in the 335-turn run the aggressive models were
eliminated progressively while steadier models survived. Figure:
`fig_deception_pay_flagship.png`. *Heavily confounded by environment RNG — frame as a
hypothesis, not a finding.*
