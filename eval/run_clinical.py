"""Run the PyPI Presidio Analyzer over the English Clinical_text notes.

Every detection is saved with its score and the recognizer that produced it,
so thresholds can be swept later in score.py without re-running Presidio.

Usage:
    python eval/run_clinical.py --name baseline                 # AnalyzerEngine() as shipped
    python eval/run_clinical.py --name trf --nlp-conf ourpresidio/conf/spacy_trf.yaml
    python eval/run_clinical.py --name ours --nlp-conf A.yaml --recognizers-conf B.yaml
    python eval/run_clinical.py --name gliner --analyzer-conf path/to/slim.yaml
    python eval/run_clinical.py --name ours_lg --ours --base lg --steps age mrn registry
Writes:
    results/<name>/predictions.jsonl   one line per detection
    results/<name>/run_info.json       versions, config and timing
"""

import argparse
import json
import logging
import platform
import sys
import time
import warnings
from importlib import metadata

from common import ENGLISH_IDS, GOLD_DIR, ROOT, RESULTS_DIR, read_jsonl, read_note, write_jsonl


class LogCapture(logging.Handler):
    """Collect every log record and warning emitted during the run (for G11)."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def start_log_capture():
    cap = LogCapture()
    logging.getLogger().addHandler(cap)
    logging.getLogger().setLevel(logging.INFO)
    warnings.simplefilter("always")  # count every warning, not just the first
    warnings.showwarning = lambda msg, cat, *a, **k: cap.messages.append(f"{cat.__name__}: {msg}")
    return cap


def count_phi_in_logs(messages):
    """How many captured messages contain a gold PHI string (names, IDs, dates...)."""
    gold = {g["text"] for g in read_jsonl(GOLD_DIR / "gold.jsonl") if len(g["text"]) >= 5}
    return sum(any(t in m for t in gold) for m in messages)


def build_engine(nlp_conf, recognizers_conf, analyzer_conf=None):
    from presidio_analyzer import AnalyzerEngine, AnalyzerEngineProvider

    if nlp_conf or recognizers_conf or analyzer_conf:
        return AnalyzerEngineProvider(
            analyzer_engine_conf_file=analyzer_conf,
            nlp_engine_conf_file=nlp_conf,
            recognizer_registry_conf_file=recognizers_conf,
        ).create_engine()
    return AnalyzerEngine()  # out-of-the-box defaults


def versions():
    out = {"python": platform.python_version()}
    for pkg in ["presidio-analyzer", "spacy", "en-core-web-lg", "en-core-web-trf",
                "transformers", "torch", "spacy-huggingface-pipelines"]:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            pass
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="run name, e.g. baseline")
    parser.add_argument("--nlp-conf", default=None)
    parser.add_argument("--recognizers-conf", default=None)
    parser.add_argument("--analyzer-conf", default=None, help="full analyzer YAML, e.g. slim.yaml")
    parser.add_argument("--ours", action="store_true", help="use ourpresidio.ClinicalAnalyzer")
    parser.add_argument("--base", default="lg", choices=["lg", "trf", "stanford"])
    parser.add_argument("--steps", nargs="*", default=None, help="ourpresidio steps (default: all)")
    args = parser.parse_args()

    cap = start_log_capture()
    t0 = time.perf_counter()
    if args.ours:
        sys.path.insert(0, str(ROOT))
        from ourpresidio.engine import ALL_STEPS, ClinicalAnalyzer

        steps = ALL_STEPS if args.steps is None else args.steps
        engine = ClinicalAnalyzer(base=args.base, steps=steps)
    else:
        engine = build_engine(args.nlp_conf, args.recognizers_conf, args.analyzer_conf)
    engine.analyze(text="warm up", language="en")
    load_s = time.perf_counter() - t0

    rows, per_note = [], []
    for note_id in ENGLISH_IDS:
        text = read_note(note_id)
        t = time.perf_counter()
        results = engine.analyze(text, language="en")
        per_note.append(time.perf_counter() - t)
        for r in results:
            meta = r.recognition_metadata or {}
            rows.append({
                "note": note_id, "start": r.start, "end": r.end,
                "text": text[r.start:r.end], "label": r.entity_type,
                "score": round(float(r.score), 4),
                "recognizer": meta.get("recognizer_name"),
            })

    out_dir = RESULTS_DIR / args.name
    write_jsonl(out_dir / "predictions.jsonl", rows)
    info = {
        "name": args.name,
        "nlp_conf": args.nlp_conf or "default (AnalyzerEngine())",
        "recognizers_conf": args.recognizers_conf or "default",
        "analyzer_conf": args.analyzer_conf,
        "ours": {"base": args.base, "steps": steps} if args.ours else None,
        "versions": versions(),
        "supported_entities": sorted(engine.get_supported_entities("en")),
        "recognizers": sorted(r.name for r in engine.registry.get_recognizers("en", all_fields=True)),
        "notes": len(ENGLISH_IDS),
        "detections": len(rows),
        "load_seconds": round(load_s, 2),
        "analyze_seconds_total": round(sum(per_note), 2),
        "ms_per_note": round(1000 * sum(per_note) / len(per_note), 1),
        "log_messages": len(cap.messages),
        "log_messages_with_phi": count_phi_in_logs(cap.messages),
    }
    with open(out_dir / "run_info.json", "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    print(f"{len(rows)} detections in {len(ENGLISH_IDS)} notes, "
          f"{info['ms_per_note']} ms/note (load {info['load_seconds']} s), "
          f"log messages with PHI: {info['log_messages_with_phi']} -> {out_dir}")


if __name__ == "__main__":
    main()
