"""Generate calibration/contrast figures from the committed verdict DBs.

Reads the sqlite verdict DBs directly (stdlib sqlite3 — no app deps) and writes
PNGs to research/calibration_20260621/figures/. Re-runnable.
"""
import sqlite3, collections, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DIR = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(DIR, "figures"); os.makedirs(FIG, exist_ok=True)

SHORT = {"anthropic/claude-opus-4.7":"Opus","openai/gpt-5":"GPT-5",
         "google/gemini-3.1-pro-preview":"Gemini","x-ai/grok-4.3":"Grok"}
COL   = {"Opus":"#7c3aed","GPT-5":"#16a34a","Gemini":"#2563eb","Grok":"#dc2626"}
ORDER = ["Opus","Gemini","GPT-5","Grok"]
CONDS = ["neutral","honesty","deception"]
CCOL  = {"neutral":"#9ca3af","honesty":"#0d9488","deception":"#dc2626"}

def load(db, pv):
    c = sqlite3.connect(db)
    amap = {a:SHORT.get(m,m) for a,m in c.execute("select agent_id,model from agents")}
    rows = c.execute("select turn,agent_id,is_deceptive,deception_type,target_id,confidence "
                     "from deception_judgments where prompt_version=?",(pv,)).fetchall()
    c.close()
    return amap, rows

# ---- gather contrast (13t, v2) ----------------------------------------------
judged = {c:collections.Counter() for c in CONDS}
decep  = {c:collections.Counter() for c in CONDS}
types  = {c:collections.Counter() for c in CONDS}
for cond in CONDS:
    amap, rows = load(os.path.join(DIR,f"contrast_{cond}.sqlite"), "v2")
    for turn,aid,isd,dt,tgt,conf in rows:
        m = amap.get(aid,"?"); judged[cond][m]+=1
        if isd: decep[cond][m]+=1; types[cond][dt]+=1

def rate(cond,m):
    j=judged[cond][m]; return 100*decep[cond][m]/j if j else 0

# ===== FIG 1: deception rate by model x condition ============================
fig,ax=plt.subplots(figsize=(8,4.8))
x=range(len(ORDER)); w=0.26
for i,cond in enumerate(CONDS):
    vals=[rate(cond,m) for m in ORDER]
    bars=ax.bar([xx+(i-1)*w for xx in x], vals, w, label=cond, color=CCOL[cond],
                edgecolor="white")
    for b,v,m in zip(bars,vals,ORDER):
        j=judged[cond][m]; d=decep[cond][m]
        ax.text(b.get_x()+b.get_width()/2, v+1, f"{d}/{j}", ha="center",
                va="bottom", fontsize=7, color="#374151")
ax.set_xticks(list(x)); ax.set_xticklabels(ORDER)
ax.set_ylabel("judged deception rate (%)"); ax.set_ylim(0,60)
ax.set_title("Judged deception rate by model × condition\n(seed 42, 13 turns, v2 Opus judge — n=1/cell, DIRECTIONAL)",
             fontsize=10)
ax.legend(title="condition", frameon=False); ax.spines[["top","right"]].set_visible(False)
ax.grid(axis="y",alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig1_condition_model_rate.png"),dpi=150); plt.close(fig)

# ===== FIG 2: deception-type mix by condition (stacked) ======================
TYPES=["false_state_claim","misdirection","strategic_omission","false_promise","identity_bluff"]
TCOL=dict(zip(TYPES,["#1d4ed8","#dc2626","#d97706","#0d9488","#7c3aed"]))
fig,ax=plt.subplots(figsize=(7,4.6))
bottoms=[0]*len(CONDS)
for t in TYPES:
    vals=[types[c][t] for c in CONDS]
    ax.bar(CONDS,vals,bottom=bottoms,label=t,color=TCOL[t],edgecolor="white")
    bottoms=[b+v for b,v in zip(bottoms,vals)]
for i,c in enumerate(CONDS):
    ax.text(i,bottoms[i]+0.2,f"n={int(bottoms[i])}",ha="center",fontsize=8,color="#374151")
ax.set_ylabel("deceptive agent-turns (count)")
ax.set_title("Deception TYPE mix shifts with the instruction\n(honesty → only subtle omission/false-state; deception → adds brazen bluff/promise)",
             fontsize=10)
ax.legend(frameon=False,fontsize=8); ax.spines[["top","right"]].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig2_type_mix.png"),dpi=150); plt.close(fig)

# ===== FIG 3 & 4 from the 25-turn calibration (v1) ===========================
amap, rows = load(os.path.join(DIR,"calib.sqlite"), "v1")
per_turn=collections.Counter();
for turn,aid,isd,dt,tgt,conf in rows:
    if isd: per_turn[turn]+=1
turns=range(1,26); counts=[per_turn[t] for t in turns]
fig,ax=plt.subplots(figsize=(8,4))
ax.bar(list(turns),counts,color="#dc2626",alpha=.85)
for tx in (10,20):
    ax.axvline(tx,ls="--",color="#6b7280",lw=1); ax.text(tx,max(counts)+.15,"tax",ha="center",fontsize=7,color="#6b7280")
ax.set_xlabel("turn"); ax.set_ylabel("deceptive agent-turns")
ax.set_title("Deception over the horizon (25-turn calibration): present from T4, sustained to T25",fontsize=10)
ax.set_xticks(list(turns)); ax.tick_params(axis="x",labelsize=7)
ax.spines[["top","right"]].set_visible(False); ax.grid(axis="y",alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig3_deception_over_time.png"),dpi=150); plt.close(fig)

# FIG 4: sustained campaigns — deceptive turns per actor, colored by target
fig,ax=plt.subplots(figsize=(9,3.8))
yrows={m:i for i,m in enumerate(ORDER)}
for turn,aid,isd,dt,tgt,conf in rows:
    if not isd: continue
    actor=amap.get(aid,"?");
    tm = amap.get(tgt,"broadcast") if tgt else "broadcast"
    y=yrows.get(actor);
    if y is None: continue
    ax.scatter(turn,y,s=120,color=COL.get(tm,"#9ca3af"),edgecolor="white",zorder=3)
ax.set_yticks(range(len(ORDER))); ax.set_yticklabels(ORDER)
ax.set_xlabel("turn"); ax.set_xlim(0,26); ax.set_xticks(range(1,26)); ax.tick_params(axis="x",labelsize=7)
ax.set_title("Sustained deception campaigns (25-turn calibration): each dot = a deceptive turn, colored by TARGET\n"
             "Opus runs a multi-turn campaign vs Grok (red) with a gap and resumption",fontsize=9.5)
handles=[plt.Line2D([0],[0],marker='o',ls='',color=COL[m],label=f"target: {m}") for m in ORDER]
handles.append(plt.Line2D([0],[0],marker='o',ls='',color="#9ca3af",label="target: broadcast/none"))
ax.legend(handles=handles,frameon=False,fontsize=8,loc="upper left",bbox_to_anchor=(1.0,1.0))
ax.spines[["top","right"]].set_visible(False); ax.grid(axis="x",alpha=.25)
fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig4_campaigns.png"),dpi=150,bbox_inches="tight"); plt.close(fig)

print("wrote figures to", FIG)
for f in sorted(os.listdir(FIG)): print("  ", f)
