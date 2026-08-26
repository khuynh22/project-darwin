"""Figures for the 10-model / 335-turn run: the H1 leaderboard and the H3 coherence panel.

Reads ``metrics_335t.json`` (written by ``analyze_coherence.py``) plus the raw
verdicts, and writes PNGs to ``figures/``. Re-runnable.

**Single-hue by design.** A 9-model categorical palette cannot pass CVD adjacent-pair
separation, so identity is carried by the axis label or the panel title, never by
colour alone. Where a second colour is needed it is a *semantic* contrast
(campaign vs one-off), not an identity code.
"""
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

DIR = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(DIR, "figures")
os.makedirs(FIG, exist_ok=True)

INK = "#1f2328"          # primary text
MUTED = "#6b7280"        # secondary text / axes
GRID = "#e5e7eb"
ACCENT = "#7c3aed"       # the single data hue (house Opus purple, reused as "the" mark colour)
ACCENT_LO = "#c4b5fd"    # same hue, recessive step — for one-off / low-salience marks
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": GRID, "font.size": 9,
})


def _despine(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)


def load():
    with open(os.path.join(DIR, "metrics_335t.json"), encoding="utf-8") as f:
        m = json.load(f)
    verdicts = [json.loads(x) for x in
                open(os.path.join(DIR, "verdicts_335t.jsonl"), encoding="utf-8") if x.strip()]
    return m, verdicts


# ---------------------------------------------------------------- leaderboard

def fig_leaderboard(m):
    rows = sorted(m["leaderboard"]["per_model"], key=lambda r: r["deception_rate"])
    names = [r["model"] for r in rows]
    rates = [100 * r["deception_rate"] for r in rows]
    alive = [r["turns_alive"] for r in rows]
    judged = [r["judged_turns"] for r in rows]
    y = range(len(rows))

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(10.5, 4.4), gridspec_kw={"width_ratios": [2.4, 1]}, sharey=True)

    ax.barh(list(y), rates, height=0.62, color=ACCENT, zorder=3)
    for i, (r, n) in enumerate(zip(rates, judged)):
        ax.text(r + 0.7, i, f"{r:.1f}%", va="center", ha="left", fontsize=8.5, color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("deceptive turns / judged turns (%)")
    ax.set_xlim(0, max(rates) * 1.18 if rates else 1)
    ax.xaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
    ax.set_title("Deception rate", fontsize=10, loc="left", color=INK)
    _despine(ax)

    # Exposure panel — the confound made visible rather than buried in a caption.
    ax2.barh(list(y), alive, height=0.62, color=ACCENT_LO, zorder=3)
    for i, (a, n) in enumerate(zip(alive, judged)):
        ax2.text(a + 6, i, f"{a}", va="center", ha="left", fontsize=8, color=MUTED)
    ax2.set_xlabel("turns survived")
    ax2.set_xlim(0, 335 * 1.2)
    ax2.xaxis.grid(True, color=GRID, zorder=0); ax2.set_axisbelow(True)
    ax2.set_title("Exposure", fontsize=10, loc="left", color=INK)
    _despine(ax2, keep=("bottom",))

    n_j, n_all = m["leaderboard"]["n_judged"], m["leaderboard"]["n_judgeable"]
    fig.suptitle(
        "Deception rate by model — 10-model free-for-all, 335 turns, neutral condition, blank personas\n"
        f"n=1 game, single seed; Opus v2 judge, K=1, {n_j}/{n_all} judgeable turns. "
        "Kimi excluded (tool-call fallbacks). Rate is exposure-normalised, but survival differs "
        "8× across models — short-lived agents are scored on their opening turns only.",
        fontsize=8.6, color=MUTED, x=0.005, ha="left", y=1.02)
    fig.tight_layout()
    p = os.path.join(FIG, "fig_leaderboard_9model.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig)
    print("wrote", p)


# ----------------------------------------------------------------- coherence

def fig_coherence(m, verdicts):
    coh = m["candidates"]["coherence"]["per_model"]
    decay = m["decay"]

    fig = plt.figure(figsize=(11.5, 9.4))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.35, 1.0, 1.0], hspace=1.02, wspace=0.24)

    # ---- (a) campaign raster: one row per (deceiver -> target) pair ----------
    axa = fig.add_subplot(gs[0, :])
    pairs = defaultdict(list)
    for v in verdicts:
        if v["is_deceptive"] and v.get("target_id"):
            pairs[(v["agent_id"], v["target_id"])].append(int(v["turn"]))
    top = sorted(pairs.items(), key=lambda kv: -len(kv[1]))[:14]
    top = sorted(top, key=lambda kv: min(kv[1]))
    for i, ((d, t), turns) in enumerate(top):
        turns = sorted(turns)
        axa.plot([min(turns), max(turns)], [i, i], color=GRID, lw=1.2, zorder=1)
        axa.scatter(turns, [i] * len(turns), s=17, color=ACCENT, zorder=3, linewidths=0)
        # Highlight resumptions: a return after >= 5 silent turns.
        for p, q in zip(turns, turns[1:]):
            if q - p - 1 >= 5:
                axa.plot([p, q], [i, i], color=ACCENT_LO, lw=2.6, zorder=2, solid_capstyle="round")
    axa.set_yticks(range(len(top)))
    axa.set_yticklabels([f"{d} → {t}" for (d, t), _ in top], fontsize=8)
    axa.set_xlabel("turn"); axa.set_xlim(0, 340)
    axa.xaxis.grid(True, color=GRID); axa.set_axisbelow(True)
    axa.set_title("(a) Directed deception campaigns — each dot is one deceptive turn; "
                  "thick bars mark a return to the same target after ≥5 silent turns",
                  fontsize=9.5, loc="left", color=INK)
    _despine(axa)
    axa.legend(handles=[
        Line2D([], [], marker="o", ls="", color=ACCENT, ms=5, label="deceptive turn"),
        Line2D([], [], color=ACCENT_LO, lw=2.6, label="silent gap ≥5 turns, later resumed"),
    ], fontsize=8, frameon=False, loc="upper right", bbox_to_anchor=(1.0, -0.16), ncol=2)

    # ---- (b),(c) observed vs permutation null -------------------------------
    # Raw campaign statistics are mechanically inflated: with few rivals alive, a
    # frequent liar MUST repeat targets. Every panel therefore plots the null
    # expectation beside the observation; only the gap is interpretable.
    null = m["null_model"]["per_model"]
    qmap = {(t["model"], t["metric"]): t for t in m["null_model"]["multiplicity"]["tests"]}

    def _obs_vs_null(ax, metric, title, xlabel, pct=False):
        items = sorted(
            [(k, v) for k, v in null.items() if metric in v],
            key=lambda kv: kv[1][metric]["observed"])
        ys = range(len(items))
        scale = 100 if pct else 1
        obs = [v[metric]["observed"] * scale for _, v in items]
        exp = [v[metric]["null_mean"] * scale for _, v in items]
        ax.barh(list(ys), obs, height=0.58, color=ACCENT, zorder=3, label="observed")
        ax.scatter(exp, list(ys), marker="|", s=260, linewidths=2.2,
                   color=INK, zorder=5, label="chance (null mean)")
        for i, (name, v) in enumerate(items):
            t = qmap.get((name, metric))
            star = " *" if t and t["significant_at_fdr_0.05"] else ""
            ax.text(max(obs[i], exp[i]) * 1.03 + 0.4, i,
                    f"q={t['q_bh']:.3f}{star}" if t else "", va="center",
                    fontsize=7.2, color=INK if star else MUTED)
        ax.set_yticks(list(ys)); ax.set_yticklabels([k for k, _ in items], fontsize=8)
        ax.set_xlim(0, max(max(obs), max(exp)) * 1.42)
        ax.set_xlabel(xlabel)
        ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
        ax.set_title(title, fontsize=9.5, loc="left", color=INK)
        _despine(ax)

    axb = fig.add_subplot(gs[1, 0])
    _obs_vs_null(axb, "repeat_target_share",
                 "(b) Target selectivity vs chance — share of directed lies\n"
                 "aimed at an already-deceived victim",
                 "repeat-target share (%)", pct=True)

    axc = fig.add_subplot(gs[1, 1])
    _obs_vs_null(axc, "max_return_gap",
                 "(c) Longest thread resumed vs chance",
                 "turns of silence before returning to the same target")

    # ---- (d) decay over the horizon — small multiples, one per survivor ------
    survivors = decay["survivors"]
    sub = gs[2, :].subgridspec(1, max(1, len(survivors)), wspace=0.32)
    for j, s in enumerate(survivors):
        axd = fig.add_subplot(sub[0, j])
        bs = decay["per_survivor_buckets"].get(s, [])
        xs = list(range(len(bs)))
        ys = [100 * b["rate"] for b in bs]
        axd.plot(xs, ys, color=ACCENT, lw=2, marker="o", ms=4)
        axd.set_xticks(xs)
        axd.set_xticklabels([b["bucket"].split("-")[0] for b in bs], fontsize=6.5, rotation=45)
        axd.set_ylim(0, max(60, max(ys) * 1.25 if ys else 60))
        slope = decay["per_survivor_slope"].get(s)
        axd.set_title(f"{s}\nslope {slope:+.4f}/turn" if slope is not None else s,
                      fontsize=8.5, color=INK)
        axd.yaxis.grid(True, color=GRID); axd.set_axisbelow(True)
        _despine(axd)
        if j == 0:
            axd.set_ylabel("deception rate (%)", fontsize=8)
        axd.set_xlabel("turn", fontsize=7.5)
    fig.text(0.005, 0.285, "(d) Does coherence decay over a long horizon? Per-turn deception rate "
             "in 50-turn buckets, survivors only (agents alive ≥300 turns).",
             fontsize=9.5, color=INK, ha="left", va="bottom")

    params = m["candidates"]["coherence"]["params"] if "params" in m["candidates"]["coherence"] else {}
    nsig = m["null_model"]["multiplicity"]["n_significant"]
    ntest = m["null_model"]["multiplicity"]["n_tests"]
    fig.suptitle(
        "Deception coherence over 335 turns — 10-model free-for-all, neutral, blank personas, "
        f"Opus v2 judge (K=1), 1600/1601 turns judged. Episode segmentation max_gap={params.get('max_gap')}.\n"
        "Raw campaign statistics are mechanically inflated — with few rivals alive a frequent liar "
        "must repeat targets — so in (b) and (c) the bar is observed and the black tick is chance "
        "under a permutation null (targets reshuffled among "
        f"agents alive that turn, 1000 iters); * = survives Benjamini-Hochberg FDR q≤0.05 across all {ntest} "
        f"tests ({nsig} do).\nn=1 game / single seed; long-horizon panels condition on survival, which is "
        "itself strategy-dependent.",
        fontsize=8.4, color=MUTED, x=0.005, ha="left", y=1.02)
    p = os.path.join(FIG, "fig_coherence_335t.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig)
    print("wrote", p)


if __name__ == "__main__":
    m, verdicts = load()
    fig_leaderboard(m)
    fig_coherence(m, verdicts)
