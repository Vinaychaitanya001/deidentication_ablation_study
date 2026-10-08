"""Print Markdown tables comparing scored runs (reads results/<name>/metrics_<split>.json).

Usage:
    python eval/compare.py --split dev baseline cfg_spacy_sm cfg_spacy_trf
"""

import argparse
import json

from common import LABELS, RESULTS_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()

    rows = []
    for name in args.runs:
        with open(RESULTS_DIR / name / f"metrics_{args.split}.json", encoding="utf-8") as fh:
            m = json.load(fh)
        with open(RESULTS_DIR / name / "run_info.json", encoding="utf-8") as fh:
            info = json.load(fh)
        rows.append((name, m, info))

    print("| Run | Any P / R / F1 | Overlap P / R / F1 | Strict F1 | PHI chars covered | Detections | ms/note |")
    print("|---|---|---|---|---|---|---|")
    for name, m, info in rows:
        a, o = m["any"]["micro"], m["overlap"]["micro"]
        print(f"| {name} | {a['precision']:.3f} / {a['recall']:.3f} / {a['f1']:.3f} "
              f"| {o['precision']:.3f} / {o['recall']:.3f} / {o['f1']:.3f} "
              f"| {m['strict']['micro']['f1']:.3f} | {m['char']['phi_char_recall']:.3f} "
              f"| {o['pred']} | {info['ms_per_note']:.0f} |")

    print("\nPer type: overlap F1 (recall under `any` in brackets)\n")
    print("| Run | " + " | ".join(LABELS) + " |")
    print("|---|" + "---|" * len(LABELS))
    for name, m, _ in rows:
        cells = []
        for lab in LABELS:
            f1 = m["overlap"]["per_label"][lab]["f1"]
            ra = m["any"]["per_label"][lab]["recall"]
            cells.append(f"{f1:.2f} ({ra:.2f})")
        print(f"| {name} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
