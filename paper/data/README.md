# Data provenance

Which run backs which number. Every figure/statistic in the paper must trace to a row here.
Raw data lives in `research/` (tracked in git, including verdict DBs); this file is the index.

| run | config | data | judged | used for |
|---|---|---|---|---|
| **Pilot** (2026-05-29) | 4 models, 50 turns, UI | `research/session_20260529_023302/` | no (pre-triple: no `public_message`) | motivation only — **not** evidence |
| **Calibration** (2026-06-21) | 4 models, 25 turns, neutral, seed 42 | `research/calibration_20260621/calib.sqlite` + `calib_thoughts.jsonl` | Opus **v1**, K=1, 99 turns | judge validation; `fig_campaigns`, `fig_type_by_model` |
| **Condition contrast** (2026-06-22) | 4 models, 13 turns × {neutral, honesty, deception}, seed 42 | `research/calibration_20260621/contrast_*.sqlite` | Opus **v2**, K=1, 154 turns | **H2**; `fig_condition_contrast`, `fig_type_mix_condition` |
| **Flagship** (2026-07-23) | **8 agents = 2× each of 4 models**, neutral, seed 42, ran to apex T85 | `research/flagship_20260723/flagship.sqlite` | Opus **v2**, K=1, 544 turns | **H1a, H4**; `fig_model_not_seat`, `fig_deception_pay_flagship` |
| **10-model leaderboard** (2026-07-26) | 10 models, **335 turns**, neutral, blank personas, UI/Postgres | `research/leaderboard_335t_20260726/thoughts_335t.jsonl` (2009 rows) | **PENDING** — 1601 judgeable rows | **H1, H3** (headline horizon) once judged |

## Caveats attached to specific runs

- **v1 vs v2 judge.** The prompt was revised (target/channel rules) after calibration; verdicts
  are cached per `(judge_model, prompt_version)` and **must not be pooled across versions**.
  Calibration is v1; everything after is v2.
- **10-model run.** Kimi excluded (56% tool-call fallbacks — instrumentation artifact).
  `skip` and fallback turns dropped. Judged from the export, so ground truth comes from the
  recorded `outcome` string rather than full DB state.
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
