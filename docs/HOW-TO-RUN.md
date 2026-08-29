# How to run Project Darwin

Everything below runs from `backend/`. The CLI is `python -m app.cli.main` (installed as
`darwin` if you `pip install -e backend`).

Two things to know before you spend anything:

1. **A run that was not recorded cannot be replayed.** Set `cache` in the experiment spec.
   The decisions are gone once the run ends; there is no way to add them afterwards.
2. **A cache is bound to the environment version that produced it.** `ENV_VERSION` is
   `darwin-2.0`. Any mechanic change bumps it and invalidates every cache recorded before,
   by design — a changed mechanic changes the world brief and therefore every prompt.

So: collect expensive data **immediately after a version tag**, never mid-phase.

---

## 0. Offline check — free, no key

Proves the whole chain works before any model is involved.

```bash
cd backend
python -m pytest tests/ -q          # 349 tests, no network, no API key
```

The end-to-end test (`tests/test_e2e_offline.py`) runs simulate → export → validate →
judge → coherence → null → FDR with stub agents and `StubJudge`. If this passes, the
mechanisms work. It says nothing about whether *models* use them.

---

## 1. Stub sweep — free

A dry run of the real pipeline, with fake agents.

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./darwin.sqlite" \
  python -m app.cli.main sweep ../experiments/pilot-darwin2.json --dry-run
```

`--dry-run` lists the cells and their derived session ids and runs nothing. Drop it (and
point `roster` at a stub roster) to actually execute.

---

## 2. Pilot — the decision point, roughly $1–3

`experiments/pilot-darwin2.json` runs 3 frontier models for 30 turns and records every
decision.

```bash
cd backend
export OPENROUTER_API_KEY=sk-...
DATABASE_URL="sqlite+aiosqlite:///./darwin.sqlite" \
  python -m app.cli.main sweep ../experiments/pilot-darwin2.json
```

**Read the pilot for three things, in this order:**

| question | how to check | why it decides the next step |
|---|---|---|
| Do models use the new actions at all? | count `sign_contract` / `declare` / `stand_for_office` in the trace | if they never do, layer 2 is dead weight and the calibration set will be empty |
| What is the tool-call failure rate? | `instrument.tool_call_ok` false share, per model | Kimi hit 56% at 20 tools; at 25 a weak model may be worse, which silently shrinks your judged sample |
| Did the prompt get unwieldy? | token spend per turn against expectations | the system prompt lists 25 actions and the brief now carries registries |

```bash
python -m app.cli.main validate ../runs/pilot-darwin2/neutral-s1.jsonl
python -m app.cli.main replay ../runs/pilot-darwin2/neutral-s1.jsonl --agent opus
```

---

## 3. Verify the replay — free

This is the reproducibility claim, tested on real data rather than stubs.

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./darwin.sqlite" \
  python -m app.cli.main replay ../runs/pilot-darwin2/neutral-s1.jsonl \
    --from-cache ../runs/pilot-darwin2/responses/neutral-s1 \
    --mode strict
```

Expect `0 misses, 0 divergences`. Anything else means the environment changed under the
cache or the cache is incomplete — find out now, not in review.

`strict` fails loudly on a miss. That matters: the engine deliberately survives an agent
raising, so without the miss counter a failed replay would quietly finish as a *different
experiment wearing the same name*.

---

## 4. Judge and calibrate — roughly $5

```bash
cd backend
python -m app.cli.main judge ../runs/pilot-darwin2/neutral-s1.jsonl \
  --out ../runs/pilot-darwin2/verdicts.jsonl \
  --judge-model anthropic/claude-opus-4.7

python -m app.cli.main calibrate ../runs/pilot-darwin2/neutral-s1.jsonl \
  --verdicts ../runs/pilot-darwin2/verdicts.jsonl
```

Judging is **resumable and safe to interrupt**: a failed verdict is never written, because
a degraded `none @ confidence 0` is indistinguishable from a real negative label and would
make resume skip the row forever. Re-run to continue.

`calibrate` is the one measurement that asks whether the judge is *right* rather than
whether two judges agree. It scores verdicts against `declare` turns, whose truth the
engine recorded by arithmetic.

**Expect `underpowered` to fire on a pilot.** The calibration set is opt-in by the agent —
nothing compels a model to declare — so a small run yields few labelled turns. That is a
signal to author probes, not to run more turns.

---

## 5. Probes — the benchmark

```bash
cd backend
python -m app.cli.main probe mine ../runs/pilot-darwin2/neutral-s1.jsonl \
  --verdicts ../runs/pilot-darwin2/verdicts.jsonl \
  --out ../probes/pilot.jsonl

python -m app.cli.main probe run ../probes/pilot.jsonl \
  --model anthropic/claude-opus-4.7 --out ../runs/probe-results.jsonl --samples 5

python -m app.cli.main probe score ../runs/probe-results.jsonl
```

Mining warns when the source trace recorded no per-turn state; probes from such a trace
carry no difficulty tier, because a tier derived from an engine default would report every
probe as "honesty is free". Traces produced by this version record full state, so they tier
properly.

`probe run` defaults to the **public** split and refuses to mix splits silently — a
leaderboard built from published and held-out probes together is uninterpretable.

---

## 6. Analyse a full run

```bash
cd research/<run-dir> && python analyze_coherence.py
```

Coherence significance is reported after Benjamini–Hochberg correction across all
model × metric tests. **Never quote an uncorrected p-value as a finding** — the headline
result of the 335-turn run failed exactly there.

---

## Docker — the whole stack

```bash
cp .env.example .env          # optional: OPENROUTER_API_KEY for an operator fallback
docker compose up --build
```

| service | address | what it is |
|---|---|---|
| arena | http://localhost:3000 | the UI: live sim, `/gallery`, `/leaderboard` |
| oracle | http://localhost:8000 | FastAPI: REST + WebSocket + `/releases` |
| postgres | internal | the ledger |

`docker compose down` stops it; `docker compose down -v` also drops the database
volume, which is how you get a clean slate.

Two things the compose file does deliberately:

- **`releases/` is mounted read-only** at `/app/releases`, with `RELEASES_DIR` set
  absolutely. The default path resolves relative to the source tree, which is not where
  the code sits inside the image — without the explicit setting the gallery silently
  serves an empty list.
- **Schema changes apply on boot.** `init_db` backfills new columns by `ALTER TABLE` and
  creates new tables, so an existing volume picks up contracts, offices, and the extended
  snapshots without a reset. Watch for `Backfilling column:` in `docker compose logs
  oracle`.

## Serving the gallery

```bash
# publish an artifact (see releases/README.md)
mkdir -p releases/<run_id>
cp runs/<run>/neutral-s1.jsonl releases/<run_id>/trace.jsonl
cp runs/<run>/verdicts.jsonl   releases/<run_id>/verdicts.jsonl

docker compose restart oracle   # the registry caches on (path, mtime)
```

The gallery is read-only and never touches the sessions tables. `/gallery` lists releases,
`/gallery/<run_id>` replays turn by turn with the triple beside the judge's verdict,
`/gallery/<run_id>/3d` replays the same run in the 3-D world with a turn scrubber, and
`/leaderboard` shows probe scores with their excluded counts and divergence.

## Replaying a run you drove from the UI

A session run from the browser writes its own trace as it goes — one turn appended after
each turn commits, so a run that is still going, or one whose process died, is still
readable.

```bash
ls runs/<session_id>/trace.jsonl                       # the file, as it grows
curl "localhost:8000/sessions/<session_id>/trace/turns?offset=0&limit=50"
darwin replay runs/<session_id>/trace.jsonl            # or: python -m app.cli.main replay ...
```

It is schema v5, the same format `/releases` serves, so everything downstream — the
judge, the metrics, probe mining — reads it without conversion. What it is *not* is a
release: the manifest declares `max_turns` as its horizon rather than the length the run
actually reached, and it has no verdicts, scores or `about.md`. Publishing means copying
it into `releases/<run_id>/` as above, which is a deliberate act and not something
pressing Step does for you.

`runs/` is gitignored and has no retention policy — abandoned sessions accumulate, so
delete them yourself. Set `RUNS_DIR` to move the directory.

**No world in the browser?** The 3-D view needs WebGL, and the page says so plainly when
it is unavailable, with links to the trace and the monologue export. Note also that the
scene does not render under `next dev` at all (React strict mode double-mounts the canvas
and the GL context is lost) — use a production build to look at it.

---

## Troubleshooting

**`no such table: contracts`** — something imported the models without importing
`app.models.registry`. `create_all` only builds tables whose module has been imported;
`init_db` does this correctly, ad-hoc scripts must do it themselves.

**A sweep runs serially despite `concurrency: 4`** — expected on SQLite, which cannot take
concurrent write transactions. Use Postgres for a parallel sweep; the clamp is logged.

**`EnvVersionMismatch` on replay** — the cache was recorded against a different
`ENV_VERSION`. There is no repair: re-record, or replay against the matching environment.

**Every contract breaches** — the agents are committing to goods they do not hold. Real
models see their inventory and the registry in the brief; if this happens with real models
it is a finding worth writing down, not a bug.
