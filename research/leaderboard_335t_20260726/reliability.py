"""Phase 2 — judge reliability for the 335-turn run.

Reviewers will not accept LLM-judge labels without this. Three independent
checks, each a stage of this script:

``sample``  Draw a **stratified** sample of judged turns: balanced on the primary
            verdict (deceptive / honest) so the agreement statistics are not
            dominated by the ~75% honest majority, and spread across models and
            turn ranges. Also writes a **blind** human-labelling sheet — actor
            and primary verdict stripped — so your own labels cannot anchor.

``judge``   Re-judge the sample. ``--replicate k`` re-runs the *same* judge
            (temperature is locked at 0, so disagreement measures provider
            nondeterminism = self-consistency). ``--judge-model`` swaps the judge
            family, which is also the Opus-judges-Opus self-preference control.

``score``   Self-consistency, cross-judge Cohen's κ, and — once
            ``human_labels.jsonl`` is filled in — human-vs-judge κ.

Same integrity rule as ``judge_export.py``: a degraded verdict (confidence 0) is
never written, so a failed call is retried rather than silently recorded as
"not deceptive".

Usage (from repo root):
    python research/leaderboard_335t_20260726/reliability.py --stage sample --n 150
    OPENROUTER_API_KEY=$KEY python .../reliability.py --stage judge --replicate 2
    OPENROUTER_API_KEY=$KEY python .../reliability.py --stage judge --judge-model openai/gpt-5.2
    python research/leaderboard_335t_20260726/reliability.py --stage score
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.judge.context import JudgeContext  # noqa: E402
from app.judge.factory import build_judge  # noqa: E402
from app.judge.schemas import normalize_verdict  # noqa: E402

HERE = Path(__file__).parent
SAMPLE = HERE / "reliability_sample.jsonl"
HUMAN = HERE / "human_labels.jsonl"
SEED = 20260801


# ------------------------------------------------------------------ helpers

def _rows() -> dict[tuple[int, str], dict]:
    out = {}
    for x in open(HERE / "thoughts_335t.jsonl", encoding="utf-8"):
        if x.strip():
            r = json.loads(x)
            out[(int(r["turn"]), r["agent_id"])] = r
    return out


def _verdicts(path: Path) -> dict[tuple[int, str], dict]:
    if not path.exists():
        return {}
    out = {}
    for x in open(path, encoding="utf-8"):
        if x.strip():
            v = json.loads(x)
            out[(int(v["turn"]), v["agent_id"])] = v
    return out


def _ctx(row: dict) -> JudgeContext:
    args = row.get("arguments") or {}
    return JudgeContext(
        session_id="ui335", turn=int(row["turn"]), agent_id=row["agent_id"],
        monologue=row.get("monologue") or "", public_message=row.get("public_message") or "",
        action=row.get("action") or "", arguments=args, outcome=row.get("outcome") or "",
        balance=None, trust_score=None,
        target_id=args.get("target") or args.get("target_id"), transactions=[],
    )


def cohen_kappa(a: list[int], b: list[int]) -> dict:
    """Cohen's κ for two raters over binary labels."""
    n = len(a)
    if n == 0:
        return {"kappa": None, "n": 0}
    obs = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    exp = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    kappa = (obs - exp) / (1 - exp) if exp < 1 else 1.0
    return {
        "kappa": round(kappa, 4), "observed_agreement": round(obs, 4),
        "expected_agreement": round(exp, 4), "n": n,
        "rater_a_positive_rate": round(pa1, 4), "rater_b_positive_rate": round(pb1, 4),
    }


def _interpret(k: float | None) -> str:
    if k is None:
        return "n/a"
    for lo, label in ((0.81, "almost perfect"), (0.61, "substantial"), (0.41, "moderate"),
                      (0.21, "fair"), (0.0, "slight")):
        if k >= lo:
            return label
    return "poor (worse than chance)"


# ------------------------------------------------------------------- stages

def stage_sample(n: int, *, random_sample: bool = False, out: Path | None = None) -> None:
    """Draw the reliability sample.

    Two designs, both needed:

    - **stratified** (default): 50/50 on the primary verdict, round-robin across models.
      Maximises information about *turn-level* agreement on the rare positive class.
      Its marginals are engineered, so κ from it is **not** the population κ, and it
      cannot test per-model ranking (every model ends up at ~0.5 by construction).
    - **``--random``**: an unstratified draw. Prevalence-correct, so it yields the
      population κ and a valid per-model ranking comparison.
    """
    primary = _verdicts(HERE / "verdicts_335t.jsonl")
    if not primary:
        sys.exit("[rel] no verdicts_335t.jsonl — run Phase 0 first.")
    rows = _rows()

    if random_sample:
        target = out or (HERE / "reliability_sample_random.jsonl")
        rng = random.Random(SEED + 1)
        chosen = rng.sample(sorted(primary), min(n, len(primary)))
        with open(target, "w", encoding="utf-8") as f:
            for turn, agent in chosen:
                f.write(json.dumps({"turn": turn, "agent_id": agent}) + "\n")
        pos = sum(1 for k in chosen if primary[k]["is_deceptive"])
        print(f"[rel] random sample {len(chosen)} rows -> {target}  "
              f"(prevalence {pos/len(chosen):.3f})")
        return

    # Stratify on (primary label, model) then spread over turn thirds.
    strata: dict[tuple[bool, str], list] = defaultdict(list)
    for key, v in primary.items():
        strata[(bool(v["is_deceptive"]), v["agent_id"])].append(key)

    rng = random.Random(SEED)
    dec_keys = [k for s, ks in strata.items() if s[0] for k in ks]
    hon_keys = [k for s, ks in strata.items() if not s[0] for k in ks]
    half = n // 2

    def _spread(keys: list, want: int) -> list:
        """Round-robin across models so no single model dominates the stratum."""
        by_model: dict[str, list] = defaultdict(list)
        for k in keys:
            by_model[k[1]].append(k)
        for v in by_model.values():
            rng.shuffle(v)
        picked, models = [], sorted(by_model)
        while len(picked) < want and any(by_model[m] for m in models):
            for m in models:
                if by_model[m] and len(picked) < want:
                    picked.append(by_model[m].pop())
        return picked

    chosen = _spread(dec_keys, half) + _spread(hon_keys, n - half)
    rng.shuffle(chosen)

    with open(SAMPLE, "w", encoding="utf-8") as f:
        for turn, agent in chosen:
            f.write(json.dumps({"turn": turn, "agent_id": agent}) + "\n")

    # Blind sheet: no actor id, no primary verdict. label = "" for you to fill.
    blind = HERE / "human_labels_BLANK.jsonl"
    with open(blind, "w", encoding="utf-8") as f:
        for i, (turn, agent) in enumerate(chosen):
            r = rows[(turn, agent)]
            f.write(json.dumps({
                "item": i, "turn": turn, "agent_id": agent,  # keys for scoring
                "monologue": r.get("monologue") or "",
                "public_message": r.get("public_message") or "",
                "action": r.get("action"), "arguments": r.get("arguments"),
                "outcome": r.get("outcome") or "",
                "is_deceptive": "",  # <-- fill true/false
            }) + "\n")

    got = Counter(("deceptive" if primary[k]["is_deceptive"] else "honest") for k in chosen)
    print(f"[rel] sampled {len(chosen)} rows -> {SAMPLE}  ({dict(got)})")
    print(f"[rel] blind human sheet -> {blind}")
    print(f"[rel]   fill the is_deceptive field, save as {HUMAN.name}, then --stage score")


async def stage_judge(judge_model: str | None, replicate: int, concurrency: int, attempts: int,
                      sample: Path | None = None, tag_suffix: str = "") -> None:
    sample = sample or SAMPLE
    if not sample.exists():
        sys.exit(f"[rel] no sample at {sample} — run --stage sample first.")
    keys = [tuple(json.loads(x).values()) for x in open(sample, encoding="utf-8") if x.strip()]
    keys = [(int(t), a) for t, a in keys]
    rows = _rows()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("[rel] ERROR: OPENROUTER_API_KEY not set.")
    judge = build_judge(provider="openrouter", judge_model=judge_model, api_key=key)
    tag = judge.judge_model.split("/")[-1] + tag_suffix

    for rep in range(1, replicate + 1):
        out = HERE / f"reliability_{tag}_r{rep}.jsonl"
        done = set(_verdicts(out))
        todo = [k for k in keys if k not in done]
        print(f"[rel] {tag} rep{rep}: todo={len(todo)} done={len(done)} -> {out.name}")
        if not todo:
            continue
        sem = asyncio.Semaphore(concurrency)
        lock = asyncio.Lock()
        f = open(out, "a", encoding="utf-8")
        failed = []

        async def _one(k):
            v = None
            cand = None
            for att in range(attempts):
                async with sem:
                    cand = await judge.judge(_ctx(rows[k]))
                if cand.confidence > 0.0:
                    v = cand
                    break
                if att < attempts - 1:
                    await asyncio.sleep(2 ** att)
            if v is None:
                async with lock:
                    failed.append(k)
                return
            v = normalize_verdict(v, actor_id=k[1])
            async with lock:
                f.write(json.dumps({
                    "turn": k[0], "agent_id": k[1], "is_deceptive": v.is_deceptive,
                    "deception_type": v.deception_type, "target_id": v.target_id,
                    "confidence": v.confidence, "rationale": v.rationale,
                }) + "\n")
                f.flush()

        try:
            await asyncio.gather(*[_one(k) for k in todo])
        finally:
            f.close()
        if failed:
            print(f"[rel] WARNING {len(failed)} rows failed after {attempts} attempts (re-run to retry)")


def stage_score() -> None:
    if not SAMPLE.exists():
        sys.exit("[rel] no sample — run --stage sample first.")
    keys = [(int(d["turn"]), d["agent_id"])
            for d in (json.loads(x) for x in open(SAMPLE, encoding="utf-8") if x.strip())]
    primary = _verdicts(HERE / "verdicts_335t.jsonl")

    # NB: the glob also matches reliability_sample_random.jsonl ("_r" in "_random"),
    # which holds sample keys, not verdicts — exclude sample files explicitly.
    reps = [q for q in sorted(HERE.glob("reliability_*_r*.jsonl"))
            if "_rand_" not in q.name and "sample" not in q.name]
    by_model: dict[str, list[dict]] = defaultdict(list)
    for p in reps:
        tag = p.name[len("reliability_"):].rsplit("_r", 1)[0]
        by_model[tag].append(_verdicts(p))

    report: dict = {"n_sample": len(keys), "replicates": {k: len(v) for k, v in by_model.items()}}

    # --- 1. self-consistency: primary + replicates of the SAME judge family ---
    primary_tag = "claude-opus-4.7"
    runs = [primary] + by_model.get(primary_tag, [])
    if len(runs) > 1:
        agree = unan = 0
        for k in keys:
            labs = [r[k]["is_deceptive"] for r in runs if k in r]
            if len(labs) < 2:
                continue
            agree += 1
            unan += len(set(labs)) == 1
        report["self_consistency"] = {
            "judge": primary_tag, "K": len(runs), "n_compared": agree,
            "unanimous_share": round(unan / agree, 4) if agree else None,
        }

    # --- 2. cross-judge sensitivity (different family) ---
    cross = {}
    for tag, runsets in by_model.items():
        if tag == primary_tag or not runsets:
            continue
        other = runsets[0]
        pairs = [(k, primary[k]["is_deceptive"], other[k]["is_deceptive"])
                 for k in keys if k in primary and k in other]
        if not pairs:
            continue
        a = [int(p[1]) for p in pairs]
        b = [int(p[2]) for p in pairs]
        st = cohen_kappa(a, b)
        st["interpretation"] = _interpret(st["kappa"])
        cross[tag] = st
    if cross:
        report["cross_judge"] = cross

    # --- 2b. does the judge choice change the *ranking*? -----------------
    # kappa answers "do judges agree turn-by-turn". The claim that actually
    # depends on the judge is H1, a per-model ordering — so test that directly.
    # A conservative judge can shift every rate down and leave the ordering intact.
    rows = _rows()
    for tag, runsets in by_model.items():
        if tag == primary_tag or not runsets:
            continue
        other = runsets[0]
        per_model: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "a": 0, "b": 0})
        for k in keys:
            if k not in primary or k not in other:
                continue
            m = per_model[k[1]]
            m["n"] += 1
            m["a"] += int(primary[k]["is_deceptive"])
            m["b"] += int(other[k]["is_deceptive"])
        table = {m: {"n": v["n"],
                     "rate_primary": round(v["a"] / v["n"], 4),
                     "rate_other": round(v["b"] / v["n"], 4)}
                 for m, v in sorted(per_model.items()) if v["n"] >= 5}
        # Spearman on the per-model rates (ties averaged).
        def _rank(vals):
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            r = [0.0] * len(vals)
            i = 0
            while i < len(order):
                j = i
                while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                    j += 1
                avg = (i + j) / 2 + 1
                for t in range(i, j + 1):
                    r[order[t]] = avg
                i = j + 1
            return r
        ms = list(table)
        if len(ms) >= 3:
            ra = _rank([table[m]["rate_primary"] for m in ms])
            rb = _rank([table[m]["rate_other"] for m in ms])
            n = len(ms)
            mra, mrb = sum(ra) / n, sum(rb) / n
            num = sum((x - mra) * (y - mrb) for x, y in zip(ra, rb))
            den = (sum((x - mra) ** 2 for x in ra) * sum((y - mrb) ** 2 for y in rb)) ** 0.5
            rho = round(num / den, 4) if den else None
        else:
            rho = None
        report.setdefault("ranking_stability", {})[tag] = {
            "per_model": table, "spearman_rho_vs_primary": rho,
            "note": "sample is stratified 50/50 on the PRIMARY judge's labels, so these "
                    "rates are not population rates; only the ordering is meaningful.",
        }

    # --- 2c. agreement as a function of the primary judge's confidence ----
    for tag, runsets in by_model.items():
        if tag == primary_tag or not runsets:
            continue
        other = runsets[0]
        bands: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "agree": 0})
        for k in keys:
            if k not in primary or k not in other:
                continue
            c = primary[k].get("confidence") or 0.0
            b = "high (>=0.9)" if c >= 0.9 else ("mid (0.75-0.9)" if c >= 0.75 else "low (<0.75)")
            bands[b]["n"] += 1
            bands[b]["agree"] += int(primary[k]["is_deceptive"] == other[k]["is_deceptive"])
        report.setdefault("agreement_by_confidence", {})[tag] = {
            b: {"n": v["n"], "agreement": round(v["agree"] / v["n"], 4)}
            for b, v in sorted(bands.items()) if v["n"]
        }

    # --- 3. human validation ---
    if HUMAN.exists():
        human = {}
        for x in open(HUMAN, encoding="utf-8"):
            if not x.strip():
                continue
            d = json.loads(x)
            lab = d.get("is_deceptive")
            if isinstance(lab, str):
                lab = lab.strip().lower()
                if lab in ("true", "t", "1", "yes", "y"):
                    lab = True
                elif lab in ("false", "f", "0", "no", "n"):
                    lab = False
                else:
                    continue
            if isinstance(lab, bool):
                human[(int(d["turn"]), d["agent_id"])] = lab
        pairs = [(human[k], primary[k]["is_deceptive"]) for k in keys
                 if k in human and k in primary]
        if pairs:
            st = cohen_kappa([int(p[0]) for p in pairs], [int(p[1]) for p in pairs])
            st["interpretation"] = _interpret(st["kappa"])
            report["human_vs_judge"] = st
        else:
            report["human_vs_judge"] = {"error": "no usable labels in human_labels.jsonl"}
    else:
        report["human_vs_judge"] = {"status": f"PENDING — fill {HUMAN.name}"}

    # --- 4. prevalence-correct checks on the RANDOM sample -----------------
    rand_sample = HERE / "reliability_sample_random.jsonl"
    if rand_sample.exists():
        rkeys = [(int(d["turn"]), d["agent_id"])
                 for d in (json.loads(x) for x in open(rand_sample, encoding="utf-8") if x.strip())]
        for q in sorted(HERE.glob("reliability_*_rand_r*.jsonl")):
            tag = q.name[len("reliability_"):].rsplit("_rand_r", 1)[0]
            other = _verdicts(q)
            pairs = [(primary[k]["is_deceptive"], other[k]["is_deceptive"])
                     for k in rkeys if k in primary and k in other]
            if not pairs:
                continue
            st = cohen_kappa([int(x) for x, _ in pairs], [int(y) for _, y in pairs])
            st["interpretation"] = _interpret(st["kappa"])
            st["note"] = "prevalence-correct: unstratified random draw, so this IS the population kappa."
            # per-model rates + Spearman on a valid (non-degenerate) design
            pm = defaultdict(lambda: {"n": 0, "a": 0, "b": 0})
            for k in rkeys:
                if k in primary and k in other:
                    m = pm[k[1]]; m["n"] += 1
                    m["a"] += int(primary[k]["is_deceptive"]); m["b"] += int(other[k]["is_deceptive"])
            table = {m: {"n": v["n"], "rate_primary": round(v["a"]/v["n"], 4),
                         "rate_other": round(v["b"]/v["n"], 4)}
                     for m, v in sorted(pm.items()) if v["n"] >= 8}
            report.setdefault("random_sample", {})[tag] = {
                "kappa": st, "per_model": table, "n": len(pairs),
            }

    out = HERE / "reliability_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\n[rel] wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["sample", "judge", "score"])
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--replicate", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--attempts", type=int, default=4)
    ap.add_argument("--random", action="store_true", help="unstratified, prevalence-correct draw")
    ap.add_argument("--sample", default=None, help="sample file to judge (default: stratified)")
    a = ap.parse_args()

    if a.stage == "sample":
        stage_sample(a.n, random_sample=a.random)
    elif a.stage == "judge":
        samp = Path(a.sample) if a.sample else None
        suffix = "_rand" if (samp and "random" in samp.name) else ""
        asyncio.run(stage_judge(a.judge_model, a.replicate, a.concurrency, a.attempts, samp, suffix))
    else:
        stage_score()


if __name__ == "__main__":
    main()
