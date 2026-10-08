#!/bin/bash
# Cumulative ablation: add one ourpresidio step at a time, score each on dev.
# Usage: bash eval/ablation.sh lg     (or trf / stanford)
BASE=${1:-lg}; PY=${PYTHON:-.venv/Scripts/python.exe}
STEPS=(age mrn registry hospital org allow post quiet)
run () { # name, steps...
  local name=$1; shift
  $PY -W ignore eval/run_clinical.py --name "$name" --ours --base "$BASE" --steps "$@" 2>/dev/null | tail -1
  $PY eval/score.py --name "$name" --split dev > /dev/null
}
run "ours_${BASE}_0_none"
cur=()
for i in "${!STEPS[@]}"; do
  cur+=("${STEPS[$i]}")
  run "ours_${BASE}_$((i+1))_${STEPS[$i]}" "${cur[@]}"
done
