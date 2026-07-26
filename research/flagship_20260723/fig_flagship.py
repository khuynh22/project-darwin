"""Flagship figures: model-vs-seat clustering + does-deception-pay (8 agents, T85 apex)."""
import sqlite3
import collections
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(DIR, "figures")
os.makedirs(FIG, exist_ok=True)
SHORT = {"anthropic/claude-opus-4.7": "Opus", "openai/gpt-5": "GPT-5",
         "google/gemini-3.1-pro-preview": "Gemini", "x-ai/grok-4.3": "Grok"}
COL = {"Opus": "#7c3aed", "GPT-5": "#16a34a", "Gemini": "#2563eb", "Grok": "#dc2626"}
ORDER = ["Opus", "Gemini", "GPT-5", "Grok"]

c = sqlite3.connect(os.path.join(DIR, "flagship.sqlite"))
amap = {a: SHORT.get(m, m) for a, m in c.execute("select agent_id,model from agents")}
agents = {a: (bal, alive, elim) for a, bal, alive, elim in
          c.execute("select agent_id,balance,alive,eliminated_at_turn from agents")}
v = c.execute("select agent_id,is_deceptive from deception_judgments "
              "where prompt_version='v2'").fetchall()
c.close()
jr = collections.Counter()
dc = collections.Counter()
for aid, isd in v:
    jr[aid] += 1
    if isd:
        dc[aid] += 1
rate = {a: 100 * dc[a] / jr[a] for a in agents if jr[a]}

# FIG A: model-vs-seat
fig, ax = plt.subplots(figsize=(8, 4.8))
x = np.arange(len(ORDER))
w = 0.34
for i, seat in enumerate(["a", "b"]):
    vals, labs = [], []
    for m in ORDER:
        aid = [a for a in agents if amap[a] == m and a.endswith("_" + seat)][0]
        vals.append(rate.get(aid, 0))
        labs.append(f"{dc[aid]}/{jr[aid]}")
    bars = ax.bar(x + (i - 0.5) * w, vals, w, label=f"instance {seat.upper()}",
                  color=[COL[m] for m in ORDER], alpha=0.95 if seat == "a" else 0.5,
                  edgecolor="white")
    for b, l in zip(bars, labs):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, l, ha="center",
                fontsize=7, color="#374151")
ax.set_xticks(x)
ax.set_xticklabels(ORDER)
ax.set_ylabel("deception rate (%)")
ax.set_ylim(0, 55)
ax.set_title("MODEL, not seat: both instances of each model land in the same band\n"
             "(flagship: 8 agents, 2 per model, 85 turns to apex — solid=A, faded=B)", fontsize=10)
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", alpha=.3)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "figA_model_vs_seat.png"), dpi=150)
plt.close(fig)

# FIG B: does deception pay
fig, ax = plt.subplots(figsize=(8, 5))
for a in agents:
    m = amap[a]
    bal, alive, elim = agents[a]
    r = rate.get(a, 0)
    ax.scatter(r, bal, s=170, color=COL[m], edgecolor="white", zorder=3)
    if not alive:
        ax.scatter([r], [bal], s=320, facecolors="none", edgecolors="black", lw=1.3, zorder=2)
    ax.annotate(a.split("agent_")[-1].upper(), (r, bal), xytext=(6, 4),
                textcoords="offset points", fontsize=8, color="#374151")
ax.set_xlabel("deception rate (%)")
ax.set_ylabel("final balance ($)")
ax.set_title("Deception did NOT pay: the apex winner (GPT-A, 13%) is one of the LEAST deceptive;\n"
             "the heaviest liars (Opus 39–45%) finished near broke. black ring = eliminated.", fontsize=9.5)
hs = [plt.Line2D([0], [0], marker='o', ls='', color=COL[m], label=m) for m in ORDER]
ax.legend(handles=hs, frameon=False, fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "figB_deception_pay.png"), dpi=150)
plt.close(fig)
print("wrote figA_model_vs_seat.png, figB_deception_pay.png")
