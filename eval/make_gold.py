"""Draft the gold-standard PHI labels for the 100 English Clinical_text notes.

Labels come from the fixed template fields (see ANNOTATION_GUIDELINE.md).
Presidio is never used here, so the gold standard is independent of the
system under test. Output is a *draft*: a human reviews it on review.html,
and the reviewed file is frozen as gold.jsonl.

Usage:
    python eval/make_gold.py
Writes:
    eval/gold/gold_draft.jsonl   one JSON line per PHI span
    eval/gold/review.html        highlighted notes for human review
"""

import json
import re
from collections import Counter

from common import ENGLISH_IDS, GOLD_DIR, read_note, write_jsonl

NAME = r"[A-Z][a-z]+(?: [A-Z][a-z]+)+"

# (label, field, regex with exactly one group = the PHI span)
FIELD_RULES = [
    ("PERSON", "patient_name", r"^Patient Name: (.+?)\s*$"),
    ("AGE", "age", r"^Age/Sex: (\d+(?: (?:months|years))?)/[MF]\s*$"),
    ("ID", "uhid", r"^UHID: (\S+)\s*$"),
    ("ID", "admission_no", r"^Admission No: (\S+)\s*$"),
    ("LOCATION", "address", r"^Address: (.+?)\s*$"),
    ("DATE_TIME", "admission_date", r"^Admission Date: (.+?)\s*$"),
    ("DATE_TIME", "discharge_date", r"^Discharge Date: (.+?)\s*$"),
    ("PERSON", "consultant", rf"^Treating Consultant: Dr\. ({NAME})"),
    ("PERSON", "signing_doctor", rf"^Dr\. ({NAME})[^\n]*\n\s*Signature\s*$"),
]
EXPECTED_SPANS = len(FIELD_RULES) + 1  # + hospital on line 1

# Words that are part of the template itself, not candidate PHI.
TEMPLATE_WORDS = {
    "Patient", "Name", "Age", "Sex", "UHID", "Admission", "No", "ADM", "Address",
    "Date", "Discharge", "Treating", "Consultant", "Dr", "Chief", "Complaints",
    "History", "Present", "Illness", "Past", "Physical", "Examination",
    "Investigations", "Diagnosis", "ICD", "Course", "Hospital", "Socio",
    "Economic", "Status", "Traditional", "Medicine", "Condition", "Advice",
    "Meds", "Diet", "Signature", "Summary", "AM", "PM", "PICCKLE", "Pallor",
    "Icterus", "Cyanosis", "Clubbing", "Koilonychia", "Lymphadenopathy", "Edema",
    "Class", "Used", "Stable", "Tab",
}


def label_note(note_id):
    text = read_note(note_id)
    spans = []

    first = re.match(r"\s*([^\r\n]+?)\s*\r?\n", text)
    spans.append(("ORGANIZATION", "hospital", first.start(1), first.end(1)))

    for label, field, pattern in FIELD_RULES:
        matches = list(re.finditer(pattern, text, flags=re.M))
        if len(matches) != 1:
            raise ValueError(f"{note_id}.txt: field {field!r} matched {len(matches)} times")
        m = matches[0]
        spans.append((label, field, m.start(1), m.end(1)))

    rows = []
    for label, field, start, end in sorted(spans, key=lambda s: s[2]):
        value = text[start:end]
        assert value == value.strip() and value, f"{note_id}: bad boundary {value!r}"
        rows.append({"note": note_id, "start": start, "end": end,
                     "text": value, "label": label, "field": field})
    if len(rows) != EXPECTED_SPANS:
        raise ValueError(f"{note_id}.txt: {len(rows)} spans, expected {EXPECTED_SPANS}")
    return text, rows


def unlabelled_capitalised(text, rows):
    """Capitalised words outside any gold span: candidates for missed PHI."""
    covered = set()
    for r in rows:
        covered.update(range(r["start"], r["end"]))
    words = []
    for m in re.finditer(r"\b[A-Z][A-Za-z]+\b", text):
        if m.start() in covered or m.group() in TEMPLATE_WORDS:
            continue
        words.append(m.group())
    return words


def main():
    all_rows, notes, candidates = [], {}, Counter()
    for note_id in ENGLISH_IDS:
        text, rows = label_note(note_id)
        all_rows.extend(rows)
        notes[note_id] = text
        candidates.update(unlabelled_capitalised(text, rows))

    write_jsonl(GOLD_DIR / "gold_draft.jsonl", all_rows)

    by_label = Counter(r["label"] for r in all_rows)
    print(f"Drafted {len(all_rows)} spans in {len(notes)} notes")
    for label, n in sorted(by_label.items()):
        print(f"  {label:<13}{n}")
    print(f"{len(candidates)} distinct capitalised words outside labels (shown on review page)")

    template = (GOLD_DIR.parent / "review_template.html").read_text(encoding="utf-8")
    payload = {
        "notes": notes,
        "spans": all_rows,
        "candidates": candidates.most_common(),
    }
    html = template.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False))
    (GOLD_DIR / "review.html").write_text(html, encoding="utf-8")
    print(f"Review page: {GOLD_DIR / 'review.html'}")


if __name__ == "__main__":
    main()
