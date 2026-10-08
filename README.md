# De-identification ablation study: Microsoft Presidio on clinical discharge summaries

How well does the **official Presidio package** (`presidio-analyzer` 2.2.364 from PyPI) find
protected health information (PHI) in Indian clinical discharge summaries, where does it fail,
and can the failures be fixed **through Presidio's own extension points, without modifying its
code**?

The full write-up is in [`report/REPORT.md`](report/REPORT.md): method, every results table,
gap analysis (G1–G14), limitations and a dated change log.

## Headline result (held-out notes 51–100, 500 PHI spans)

| System | F1 (any type) | F1 (exact span) | PHI missed | False alarms | Speed (CPU) |
|---|---|---|---|---|---|
| Presidio default, as shipped | 0.777 | 0.392 | 82 | 288 | 38 ms/note |
| **Ours-fast** (same model + our plug-ins) | **0.993** | **0.951** | **2** | **5** | 45 ms/note |
| **Ours-accurate** (transformer model + plug-ins) | **1.000** | **0.963** | **0** | **0** | 596 ms/note |

Dev notes (1–50) were used to find gaps and build fixes; test notes (51–100) were scored once,
at the end. The notes all come from **one template**, so the results do not show how the system
behaves on differently formatted notes (see the limitations in the report).

## What is here

```
report/REPORT.md        full report
eval/                   annotation guideline, gold-standard tooling, runner, scorer, comparison, timing
  gold/                 gold.jsonl (1,000 spans, frozen), draft, corrections and change record
ourpresidio/            our plug-ins: recognizers.py, clinical_vocab.py, engine.py, conf/*.yaml
results/                predictions, metrics (dev and test), error lists and timing for every run
data/Clinical_text/     the 100 English notes (see data/README.md)
docs/                   PRESIDIO_ARCHITECTURE.md (how Presidio is built)
```

## Run it

Python 3.14 (the version used for the results); other recent versions will likely work but were not tested.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt     # Windows; use .venv/bin/python elsewhere

.venv/Scripts/python.exe eval/run_clinical.py --name baseline            # Presidio as shipped
.venv/Scripts/python.exe eval/score.py --name baseline --split dev
.venv/Scripts/python.exe eval/run_clinical.py --name ours_lg_final --ours --base lg \
    --steps age mrn registry hospital allow post quiet                   # Ours-fast
.venv/Scripts/python.exe eval/score.py --name ours_lg_final --split test
.venv/Scripts/python.exe eval/compare.py --split test baseline ours_lg_final
```

Shell drivers (`eval/run_all_ablations.sh`, `eval/ablation.sh`) accept `PYTHON=...` to point at
another interpreter. The remaining commands are in report section 9.

Speeds in the report were measured on one laptop CPU (no GPU); expect different absolute values
elsewhere.
