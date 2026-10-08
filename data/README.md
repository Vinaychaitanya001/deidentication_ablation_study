# Data

`Clinical_text/1.txt` … `100.txt` — 100 synthetic English discharge summaries from Indian
hospitals (one template, Hinglish phrases in the history). Files keep their original Windows
(`\r\n`) line endings: all character offsets in `eval/gold/gold.jsonl` depend on that.

The original `Clinical_text` set also contains 62 German clinical letters (GraSCCo-style). They
are **not** included here: they are not evaluated yet, and the original source's licence terms
should be confirmed before redistributing them.

The gold-standard labels are in `eval/gold/` (see `eval/ANNOTATION_GUIDELINE.md`). No real
patient data is used anywhere in this repository.
