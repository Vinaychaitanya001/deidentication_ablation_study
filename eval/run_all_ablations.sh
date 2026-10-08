#!/bin/bash
# Full ablation on each base model, plus each base's "final" step set.
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/Scripts/python.exe}
for B in lg trf stanford; do
  rm -rf results/ours_${B}_*
  bash eval/ablation.sh $B
  for V in final final_org; do
    if [ $V = final ]; then S="age mrn registry hospital allow post quiet"; else S="age mrn registry hospital org allow post quiet"; fi
    $PY -W ignore eval/run_clinical.py --name ours_${B}_$V --ours --base $B --steps $S 2>/dev/null | tail -1
    $PY eval/score.py --name ours_${B}_$V --split dev > /dev/null
  done
done
echo ALL DONE
