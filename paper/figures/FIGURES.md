# Figures — provenance and the claim each supports

**Frozen copies.** These are snapshots, not live outputs: re-running analysis must never
silently change a figure the text describes. To update one, regenerate in `research/`, then
deliberately re-copy here and re-check the caption.

| file | claim | source run | generator |
|---|---|---|---|
| `fig_model_not_seat.png` | **H1a** — deception clusters by model, not seat/luck. Both Opus instances 39%/45%, both Grok 0%/6% under different specialties, rivals, and fates. | flagship: 8 agents (2×/model), neutral, seed 42, 85 turns to apex, v2 Opus judge | `research/flagship_20260723/fig_flagship.py` |
| `fig_deception_pay_flagship.png` | **H4** — deception did not pay. Apex winner GPT-A took $173 at 13% deception vs 26% field mean; heaviest liars (Opus 39–45%) near broke. | same as above | same |
| `fig_condition_contrast.png` | **H2** — honesty instruction lowers deception (ALL 24%→14%); "may deceive" barely moves it (→25%). | contrast: seed 42, 13 turns, 3 conditions, v2 Opus judge | `research/calibration_20260621/make_figures.py` |
| `fig_type_mix_condition.png` | **H2 (style)** — instruction changes the *kind*: honesty leaves only subtle omission/false-state; deception adds identity_bluff/false_promise. | same | same |
| `fig_campaigns.png` | **H3 (illustration)** — sustained targeted campaigns; Opus→Grok across 10 turns with a gap and resumption. | 25-turn calibration, v1 judge | same |
| `fig_type_by_model.png` | **E1** — per-model deception *signature*: Opus = false_state_claim; Gemini = broadest repertoire, only user of identity_bluff/false_promise. | pooled 3 conditions, v2 judge | `research/calibration_20260621/analyze.py` |
| `fig_leaderboard_9model.png` | **H1** — 9-model deception rate, exposure-normalised, with a second panel showing turns survived (36–335, a ~9× spread) so the exposure confound is visible rather than buried. Note GPT-5 is **not** low here, unlike the 4-model games. | 10-model / 335-turn run, neutral, blank personas, v2 Opus judge, 1600/1601 turns | `research/leaderboard_335t_20260726/fig_coherence.py` |
| `fig_coherence_335t.png` | **H3 / H3a–e** — coherence vs a permutation null. (a) campaign raster; (b) target selectivity vs chance; (c) longest resumed thread vs chance; (d) rate by 50-turn bucket for survivors. The headline is that most raw coherence is **mechanical**: only 4 of 24 tests survive BH-FDR. | same | same |

## Still to make

- `fig_environment.png` — **schematic**: turn loop + the private/public/action triple + judge. Hand-drawn; the single most useful figure for a reader who has never seen the setup. `TODO(make)`

## Caveats these two figures MUST carry (already in their captions)

- **Exposure.** Survival spans 36–335 turns; short-lived agents are scored on opening turns only.
- **Null model.** Raw repeat-target share is mechanically forced by lie volume ÷ pool size — the
  four heaviest deceivers sit *at or below* chance. Never show the raw bar without the null tick.
- **Multiplicity.** Significance is post-Benjamini-Hochberg across all 24 model×metric tests.
  Opus's 200-turn resumption (p=0.018, **q=0.072**) is *not* significant and must not be starred.
- **Kimi.** The four longest episodes all target the tool-call-impaired agent, so episode-length
  results are partly an instrumentation artifact.
- **Single-hue palette.** Both figures use one data hue; identity is carried by axis label or
  panel title. A 9-model categorical palette cannot pass CVD adjacent-pair separation, and
  reassigning the 4-model house colours would break consistency with the earlier figures.

## Caption rules

1. State the **caveat in the caption** (n=1, seed, turn count, judge version) — a figure is often read alone.
2. Never label a directional result as though it were significant. No error bars ⇒ no "significantly".
3. Name the judge + prompt version; v1 and v2 verdicts are not interchangeable.
