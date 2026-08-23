# releases/

Published artifacts, served read-only by the Oracle at `/releases` and rendered by
the gallery. One directory per release:

```
releases/<run_id>/trace.jsonl      schema v4, required
                 /verdicts.jsonl   optional
                 /scores.json      optional (probe ModelScore rows)
                 /about.md         optional, shown on the gallery card
```

`trace.jsonl` and `verdicts.jsonl` are **not committed** — they are copies of
artifacts that already live under `research/`, and duplicating them doubles the
repo for no benefit. `about.md` is committed, because it is the only part written
by hand.

Populate a release before serving the gallery:

```bash
mkdir -p releases/leaderboard_335t_20260726
cp research/leaderboard_335t_20260726/trace_335t.v4.jsonl \
   releases/leaderboard_335t_20260726/trace.jsonl
cp research/leaderboard_335t_20260726/verdicts_335t.jsonl \
   releases/leaderboard_335t_20260726/verdicts.jsonl
```

Verify what you published before pointing anyone at it:

```bash
cd backend && python -m app.cli.main validate ../releases/<run_id>/trace.jsonl
```

Override the directory with `RELEASES_DIR` if you keep artifacts elsewhere.
