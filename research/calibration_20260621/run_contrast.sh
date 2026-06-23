#!/usr/bin/env bash
# Condition contrast: neutral / honesty / deception at seed 42, v2 Opus judge.
# Fresh 13-turn games per condition, each in its own sqlite DB. Budget-guarded:
# skip a condition if remaining credit < $3.5 so it can never exhaust mid-run.
cd /d/src/project-darwin/backend || exit 1
KEY=$(grep -E '^OPENROUTER_API_KEY=' /d/src/project-darwin/.env | cut -d= -f2- | tr -d '\r"')
export OPENROUTER_API_KEY="$KEY"
DIR=/d/src/project-darwin/research/calibration_20260621
ROSTER=D:/src/project-darwin/research/calibration_20260621/roster.json
TURNS=13
SEED=42

balance() {  # ACCOUNT prepaid credit balance — NOT the key spend-cap (/key limit_remaining lies)
  curl -s https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $KEY" \
    | python -c "import sys,json;d=json.load(sys.stdin)['data'];print(round(d['total_credits']-d['total_usage'],3))"
}

# neutral (13t, v2) already completed cleanly — re-run only the two missing cells.
for COND in honesty deception; do
  REM=$(balance)
  STOP=$(python -c "print(1 if float('$REM')<3.5 else 0)" 2>/dev/null || echo 0)
  if [ "$STOP" = "1" ]; then echo "### LOW BUDGET (\$$REM) -- skipping $COND and rest"; break; fi
  echo "### CONDITION: $COND  (remaining \$$REM)"
  DB="sqlite+aiosqlite:///D:/src/project-darwin/research/calibration_20260621/contrast_${COND}.sqlite"
  DATABASE_URL="$DB" python -u -m scripts.run_simulation --turns $TURNS --reset --seed $SEED \
      --condition "$COND" --roster "$ROSTER" --out "${DIR}/contrast_${COND}_thoughts.jsonl"
  echo "### judging $COND (remaining \$$(balance))"
  DATABASE_URL="$DB" python -u -m scripts.judge_deception --session cli \
      --provider openrouter --samples 1
done
echo "### CONTRAST DONE  (remaining \$$(balance))"
