"""Shared helpers for the Clinical_text evaluation.

Every script reads notes through `read_note` so that the gold standard and
Presidio see byte-for-byte identical strings and offsets line up.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "data" / "Clinical_text"
GOLD_DIR = Path(__file__).resolve().parent / "gold"
RESULTS_DIR = ROOT / "results"

ENGLISH_IDS = [str(i) for i in range(1, 101)]
SPLITS = {
    "dev": [str(i) for i in range(1, 51)],
    "test": [str(i) for i in range(51, 101)],
    "all": ENGLISH_IDS,
}

LABELS = ["PERSON", "AGE", "DATE_TIME", "ID", "LOCATION", "ORGANIZATION"]


def read_note(note_id):
    """Return the note text exactly as stored (newline='' keeps \\r\\n)."""
    with open(NOTES_DIR / f"{note_id}.txt", encoding="utf-8", newline="") as fh:
        return fh.read()


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
