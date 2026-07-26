#!/usr/bin/env bash
# Flagship long-horizon run: 8 agents (2x each frontier model, paired personalities),
# 100 turns, neutral, seed 42, Opus v2 judge K=1.
# Budget-guarded on ACCOUNT credits (/api/v1/credits — the ledger that actually runs out).
cd /d/src/project-darwin/backend || exit 1
KEY=$(grep -E '^OPENROUTER_API_KEY=' /d/src/project-darwin/.env | cut -d= -f2- | tr -d '\r"')
export OPENROUTER_API_KEY="$KEY"
DIR=/d/src/project-darwin/research/flagship_20260723
ROSTER=D:/src/project-darwin/research/flagship_20260723/roster8.json
DB="sqlite+aiosqlite:///D:/src/project-darwin/research/flagship_20260723/flagship.sqlite"

balance() {  # ACCOUNT prepaid credits, NOT the key spend-cap
  curl -s https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $KEY" \
    | python -c "import sys,json;d=json.load(sys.stdin)['data'];print(round(d['total_credits']-d['total_usage'],3))"
}

REM=$(balance)
if python -c "exit(0 if float('$REM')>=60 else 1)" 2>/dev/null; then
  echo "### start: account balance \$$REM"
else
  echo "### ABORT: account balance \$$REM < \$60 -- add credits at openrouter.ai/settings/credits"
  exit 1
fi

DATABASE_URL="$DB" python -u -m scripts.run_simulation --turns 100 --reset --seed 42 \
    --condition neutral --roster "$ROSTER" --out "${DIR}/flagship_thoughts.jsonl"

REM=$(balance); echo "### sim done: balance \$$REM"
if python -c "exit(0 if float('$REM')>=25 else 1)" 2>/dev/null; then
  DATABASE_URL="$DB" python -u -m scripts.judge_deception --session cli \
      --provider openrouter --samples 1
else
  echo "### SKIP JUDGE: balance \$$REM < \$25 -- top up, then re-run only the judge step"
fi
echo "### FLAGSHIP DONE  (balance \$$(balance))"
