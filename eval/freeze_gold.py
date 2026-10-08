"""Apply the reviewer's corrections to the draft and freeze gold.jsonl.

Usage:
    python eval/freeze_gold.py                      # uses eval/gold/corrections.json
    python eval/freeze_gold.py --corrections path/to/corrections.json
Writes:
    eval/gold/gold.jsonl        the frozen gold standard
    eval/gold/changes.jsonl     every removal/addition applied, for the record
"""

import argparse
import json
import sys

from common import ENGLISH_IDS, GOLD_DIR, read_jsonl, read_note, write_jsonl


def key(span):
    return (span["note"], span["start"], span["end"], span["label"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corrections", default=str(GOLD_DIR / "corrections.json"))
    parser.add_argument("--force", action="store_true", help="freeze even if notes are unreviewed")
    args = parser.parse_args()

    draft = read_jsonl(GOLD_DIR / "gold_draft.jsonl")
    with open(args.corrections, encoding="utf-8") as fh:
        corr = json.load(fh)["notes"]

    unreviewed = [i for i in ENGLISH_IDS if not corr.get(i, {}).get("status")]
    if unreviewed and not args.force:
        sys.exit(f"{len(unreviewed)} notes not reviewed (e.g. {unreviewed[:5]}); use --force to freeze anyway")

    removed = {key(s) for c in corr.values() for s in c.get("removed", [])}
    gold, changes = [], []
    for span in draft:
        if key(span) in removed:
            changes.append({"action": "removed", **span})
        else:
            gold.append(span)

    for note_id, c in corr.items():
        text = read_note(note_id)
        for a in c.get("added", []):
            if text[a["start"]:a["end"]] != a["text"]:
                sys.exit(f"{note_id}: added span offsets do not match text {a!r}")
            span = {"note": note_id, "start": a["start"], "end": a["end"],
                    "text": a["text"], "label": a["label"], "field": "reviewer_added"}
            gold.append(span)
            changes.append({"action": "added", **span})

    gold.sort(key=lambda s: (int(s["note"]), s["start"]))
    write_jsonl(GOLD_DIR / "gold.jsonl", gold)
    write_jsonl(GOLD_DIR / "changes.jsonl", changes)
    comments = {i: c["comment"] for i, c in corr.items() if c.get("comment")}
    print(f"Frozen {len(gold)} spans ({len(changes)} changes from draft) -> {GOLD_DIR / 'gold.jsonl'}")
    if comments:
        print("Reviewer comments:")
        for i, text in comments.items():
            print(f"  {i}.txt: {text}")


if __name__ == "__main__":
    main()
