"""Score a Presidio run against the frozen gold standard.

Three matching rules (see the plan):
  strict   same label and exactly the same start/end
  overlap  same label and the spans overlap
  any      spans overlap, label ignored ("was the PHI hidden at all?")
plus character-level coverage of PHI (how many PHI characters would leak).

Usage:
    python eval/score.py --name baseline --split dev
    python eval/score.py --name baseline --split test --gold eval/gold/gold.jsonl
Writes (in results/<name>/):
    metrics_<split>.json   all numbers
    metrics_<split>.csv    per-label table
    errors_<split>.jsonl   every missed PHI (FN) and false alarm (FP), with context
"""

import argparse
import csv
import json
from collections import defaultdict

from common import GOLD_DIR, LABELS, RESULTS_DIR, SPLITS, read_jsonl, read_note, write_jsonl

# Presidio entity type -> gold label. Identifier-style types count as ID.
# Types with no gold equivalent keep their own name: they are false alarms
# under typed matching but can still "hide" PHI under the `any` rule.
LABEL_MAP = {
    "PERSON": "PERSON", "AGE": "AGE", "DATE_TIME": "DATE_TIME",
    "LOCATION": "LOCATION", "ORGANIZATION": "ORGANIZATION", "ID": "ID",
    "US_SSN": "ID", "US_ITIN": "ID", "US_PASSPORT": "ID", "US_DRIVER_LICENSE": "ID",
    "US_BANK_NUMBER": "ID", "UK_NHS": "ID", "MEDICAL_LICENSE": "ID",
    "IN_PAN": "ID", "IN_AADHAAR": "ID", "IN_PASSPORT": "ID", "IN_VOTER": "ID",
    "MEDICAL_RECORD_NUMBER": "ID", "MRN": "ID", "UHID": "ID",
}
THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]


def prf(tp_p, n_pred, tp_g, n_gold):
    """Precision from matched predictions, recall from matched gold spans."""
    p = tp_p / n_pred if n_pred else 0.0
    r = tp_g / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "pred": n_pred, "gold": n_gold, "pred_matched": tp_p, "gold_matched": tp_g}


def overlaps(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]


def match(gold, pred, rule):
    """Return (set of matched gold indices, set of matched pred indices)."""
    mg, mp = set(), set()
    by_note = defaultdict(list)
    for j, p in enumerate(pred):
        by_note[p["note"]].append(j)
    for i, g in enumerate(gold):
        for j in by_note[g["note"]]:
            p = pred[j]
            if rule == "strict":
                ok = (p["start"], p["end"], p["label"]) == (g["start"], g["end"], g["label"])
            elif rule == "overlap":
                ok = p["label"] == g["label"] and overlaps(p, g)
            else:  # any
                ok = overlaps(p, g)
            if ok:
                mg.add(i)
                mp.add(j)
    return mg, mp


def evaluate(gold, pred, rule):
    mg, mp = match(gold, pred, rule)
    out = {"micro": prf(len(mp), len(pred), len(mg), len(gold)), "per_label": {}}
    if rule != "any":
        labels = LABELS + sorted({p["label"] for p in pred} - set(LABELS))
        for lab in labels:
            gi = [i for i, g in enumerate(gold) if g["label"] == lab]
            pj = [j for j, p in enumerate(pred) if p["label"] == lab]
            out["per_label"][lab] = prf(len(mp.intersection(pj)), len(pj),
                                        len(mg.intersection(gi)), len(gi))
    else:
        for lab in LABELS:  # recall only: which gold labels got hidden at all
            gi = [i for i, g in enumerate(gold) if g["label"] == lab]
            out["per_label"][lab] = {"recall": round(len(mg.intersection(gi)) / len(gi), 4) if gi else 0.0,
                                     "gold": len(gi), "gold_matched": len(mg.intersection(gi))}
    return out, mg, mp


def char_coverage(gold, pred, notes):
    """Share of PHI characters covered by any prediction, and share of predicted chars that are PHI."""
    phi_total = phi_hit = pred_total = pred_phi = 0
    for n in notes:
        g = set().union(*[range(s["start"], s["end"]) for s in gold if s["note"] == n] or [set()])
        p = set().union(*[range(s["start"], s["end"]) for s in pred if s["note"] == n] or [set()])
        phi_total += len(g); phi_hit += len(g & p)
        pred_total += len(p); pred_phi += len(g & p)
    return {"phi_chars": phi_total, "phi_chars_covered": phi_hit,
            "phi_char_recall": round(phi_hit / phi_total, 4) if phi_total else 0.0,
            "pred_char_precision": round(pred_phi / pred_total, 4) if pred_total else 0.0}


def context(note_text, start, end, width=30):
    left = note_text[max(0, start - width):start].replace("\r", "").replace("\n", " ")
    right = note_text[end:end + width].replace("\r", "").replace("\n", " ")
    return f"{left}[[{note_text[start:end]}]]{right}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--split", default="dev", choices=list(SPLITS))
    parser.add_argument("--gold", default=str(GOLD_DIR / "gold.jsonl"))
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="drop predictions scoring below this before matching")
    args = parser.parse_args()

    notes = set(SPLITS[args.split])
    run_dir = RESULTS_DIR / args.name
    gold = [g for g in read_jsonl(args.gold) if g["note"] in notes]
    raw = [p for p in read_jsonl(run_dir / "predictions.jsonl") if p["note"] in notes]
    for p in raw:
        p["presidio_label"] = p["label"]
        p["label"] = LABEL_MAP.get(p["label"], p["label"])
    pred = [p for p in raw if p["score"] >= args.threshold]

    results = {"run": args.name, "split": args.split, "notes": len(notes),
               "threshold": args.threshold, "gold_file": args.gold}
    for rule in ["strict", "overlap", "any"]:
        results[rule], mg, mp = evaluate(gold, pred, rule)
        if rule == "any":
            any_mg = mg
        if rule == "overlap":
            ov_mg, ov_mp = mg, mp
    results["char"] = char_coverage(gold, pred, notes)

    sweep = []
    for t in THRESHOLDS:
        sub = [p for p in raw if p["score"] >= t]
        ov, _, _ = evaluate(gold, sub, "overlap")
        an, _, _ = evaluate(gold, sub, "any")
        sweep.append({"threshold": t, "overlap": ov["micro"], "any": an["micro"]})
    results["threshold_sweep"] = sweep

    # Errors (overlap rule): missed PHI and false alarms, with context.
    texts = {n: read_note(n) for n in notes}
    errors = []
    for i, g in enumerate(gold):
        if i not in ov_mg:
            errors.append({"type": "FN", "hidden_by_other_label": i in any_mg,
                           "note": g["note"], "label": g["label"], "field": g.get("field"),
                           "text": g["text"], "context": context(texts[g["note"]], g["start"], g["end"])})
    for j, p in enumerate(pred):
        if j not in ov_mp:
            errors.append({"type": "FP", "note": p["note"], "label": p["label"],
                           "presidio_label": p["presidio_label"], "recognizer": p.get("recognizer"),
                           "score": p["score"], "text": p["text"],
                           "context": context(texts[p["note"]], p["start"], p["end"])})
    write_jsonl(run_dir / f"errors_{args.split}.jsonl", errors)

    with open(run_dir / f"metrics_{args.split}.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    with open(run_dir / f"metrics_{args.split}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rule", "label", "precision", "recall", "f1", "gold", "pred"])
        for rule in ["strict", "overlap"]:
            for lab, m in results[rule]["per_label"].items():
                w.writerow([rule, lab, m["precision"], m["recall"], m["f1"], m["gold"], m["pred"]])
            m = results[rule]["micro"]
            w.writerow([rule, "ALL", m["precision"], m["recall"], m["f1"], m["gold"], m["pred"]])
        for lab, m in results["any"]["per_label"].items():
            w.writerow(["any", lab, "", m["recall"], "", m["gold"], ""])
        m = results["any"]["micro"]
        w.writerow(["any", "ALL", m["precision"], m["recall"], m["f1"], m["gold"], m["pred"]])

    # Console summary
    print(f"\n{args.name} | split={args.split} ({len(notes)} notes) | threshold={args.threshold}")
    print(f"{'rule':<8}{'P':>8}{'R':>8}{'F1':>8}{'gold':>7}{'pred':>7}")
    for rule in ["strict", "overlap", "any"]:
        m = results[rule]["micro"]
        print(f"{rule:<8}{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}{m['gold']:>7}{m['pred']:>7}")
    c = results["char"]
    print(f"PHI characters covered: {c['phi_chars_covered']}/{c['phi_chars']} = {c['phi_char_recall']:.3f}")
    print(f"\nper label (overlap rule) + recall under 'any':")
    print(f"{'label':<14}{'P':>8}{'R':>8}{'F1':>8}{'gold':>7}{'pred':>7}{'R_any':>8}")
    for lab, m in results["overlap"]["per_label"].items():
        ra = results["any"]["per_label"].get(lab, {}).get("recall", "")
        ra = f"{ra:>8.3f}" if ra != "" else f"{'-':>8}"
        print(f"{lab:<14}{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}{m['gold']:>7}{m['pred']:>7}{ra}")
    print(f"\nerrors -> {run_dir / f'errors_{args.split}.jsonl'}")


if __name__ == "__main__":
    main()
