# Data provenance

Which run backs which number. Every figure/statistic in the paper must trace to a row here.
Raw data lives in `research/` (tracked in git, including verdict DBs); this file is the index.

| run | config | data | judged | used for |
|---|---|---|---|---|
| **Pilot** (2026-05-29) | 4 models, 50 turns, UI | `research/session_20260529_023302/` | no (pre-triple: no `public_message`) | motivation only — **not** evidence |
| **Calibration** (2026-06-21) | 4 models, 25 turns, neutral, seed 42 | `research/calibration_20260621/calib.sqlite` + `calib_thoughts.jsonl` | Opus **v1**, K=1, 99 turns | judge validation; `fig_campaigns`, `fig_type_by_model` |
| **Condition contrast** (2026-06-22) | 4 models, 13 turns × {neutral, honesty, deception}, seed 42 | `research/calibration_20260621/contrast_*.sqlite` | Opus **v2**, K=1, 154 turns | **H2**; `fig_condition_contrast`, `fig_type_mix_condition` |
| **Flagship** (2026-07-23) | **8 agents = 2× each of 4 models**, neutral, seed 42, ran to apex T85 | `research/flagship_20260723/flagship.sqlite` | Opus **v2**, K=1, 544 turns | **H1a, H4**; `fig_model_not_seat`, `fig_deception_pay_flagship` |
| **10-model leaderboard** (2026-07-26) | 10 models, **335 turns**, neutral, blank personas, UI/Postgres | `research/leaderboard_335t_20260726/thoughts_335t.jsonl` (2009 rows) | Opus **v2**, K=1, **1601 judged** (2026-08-01) → `verdicts_335t.jsonl` | **H1, H3** (headline horizon); `fig_leaderboard_9model`, `fig_coherence_335t` |
| **Judge reliability** (2026-08-01) | stratified sample of the above; K=3 same-judge + second judge family + human labels | `research/leaderboard_335t_20260726/reliability_*.jsonl` | — | **M4**; κ and self-consistency reported in §4 |

## Caveats attached to specific runs

- **v1 vs v2 judge.** The prompt was revised (target/channel rules) after calibration; verdicts
  are cached per `(judge_model, prompt_version)` and **must not be pooled across versions**.
  Calibration is v1; everything after is v2.
- **10-model run.** Kimi excluded **as a deceiver** (56% tool-call fallbacks — instrumentation
  artifact); it remains alive in the world and is still a valid *target* of others' deception,
  so it appears on the target axis of the coherence figure. `skip` and fallback turns dropped.
  Judged from the export, so ground truth comes from the recorded `outcome` string rather than
  full DB state.
- **Unequal exposure.** Survival in this run ranges from 36 turns (qwen) to 335 (sonnet,
  gemini, gpt_5) — a ~9× spread. Deception *rates* are exposure-normalised (deceptive turns /
  judged turns), but short-lived agents are scored only on their opening turns, when the
  economy is uncrowded. Long-horizon coherence is necessarily conditioned on survival, and
  survival is itself strategy-dependent; treat cross-model coherence gaps as confounded.
- **Failed judge calls are never persisted.** `judge_export.py` retries a degraded verdict
  (confidence 0) and leaves it unwritten rather than recording a false "not deceptive", so a
  mid-run cutoff cannot silently bias the labels toward honesty. A run is complete only when
  its `todo` count reaches 0.
- **Flagship personas.** Each model had a *different* personality, so persona is confounded
  with model there; the 10-model run used **blank personas** and is the cleaner cross-model test.
- **Environment RNG.** Specialties and yields are random per agent; same-model instances can
  diverge wildly in outcome (e.g. $173.17 vs $1.20).

## Reproduction

```bash
# a seeded game (CLI, sqlite)
DATABASE_URL=sqlite+aiosqlite:///run.sqlite python -m scripts.run_simulation \
  --turns N --reset --seed 42 --condition neutral --roster roster.json

# judge it
DATABASE_URL=... python -m scripts.judge_deception --session cli --provider openrouter

# judge a UI export instead (no DB)
python research/leaderboard_335t_20260726/judge_export.py --provider openrouter
```

Environment determinism is seeded; **LLM sampling is not** — report variance over seeds,
never byte-identical reruns.
