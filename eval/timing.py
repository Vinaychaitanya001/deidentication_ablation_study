"""Re-measure speed of each system on an idle machine (CPU only).

For each system: load once, warm up, then analyze all 100 English notes
`--passes` times; report load time and median ms/note across passes.
Run with nothing else using the CPU.

Usage:
    python eval/timing.py
Writes:
    results/timing.json
"""

import argparse
import json
import platform
import statistics
import sys
import time
import warnings

from common import ENGLISH_IDS, ROOT, RESULTS_DIR, read_note

sys.path.insert(0, str(ROOT))

FINAL_STEPS = ["age", "mrn", "registry", "hospital", "allow", "post", "quiet"]

SYSTEMS = [
    ("baseline", {}),
    ("ours_lg_final", {"ours": "lg"}),
    ("cfg_spacy_trf", {"nlp": "ourpresidio/conf/spacy_trf.yaml"}),
    ("ours_trf_final", {"ours": "trf"}),
    ("cfg_stanford_deid", {"nlp": "transformers.yaml"}),
    ("ours_stanford_final", {"ours": "stanford"}),
    ("cfg_gliner", {"analyzer": "slim.yaml", "passes": 1}),
]


def conf_path(name):
    """Bare file name -> Presidio's bundled conf; anything else -> relative to the project."""
    from pathlib import Path

    import presidio_analyzer

    if "/" in name:
        return str(ROOT / name)
    return str(Path(presidio_analyzer.__file__).parent / "conf" / name)


def build(spec):
    from presidio_analyzer import AnalyzerEngine, AnalyzerEngineProvider

    if "ours" in spec:
        from ourpresidio.engine import ClinicalAnalyzer

        return ClinicalAnalyzer(base=spec["ours"], steps=FINAL_STEPS)
    if "nlp" in spec:
        return AnalyzerEngineProvider(nlp_engine_conf_file=conf_path(spec["nlp"])).create_engine()
    if "analyzer" in spec:
        return AnalyzerEngineProvider(analyzer_engine_conf_file=conf_path(spec["analyzer"])).create_engine()
    return AnalyzerEngine()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    warnings.simplefilter("ignore")

    texts = [read_note(n) for n in ENGLISH_IDS]
    out = {"machine": platform.processor() or platform.machine(), "python": platform.python_version(),
           "notes": len(texts), "systems": {}}
    for name, spec in SYSTEMS:
        if args.only and name not in args.only:
            continue
        t0 = time.perf_counter()
        engine = build(spec)
        engine.analyze("warm up", language="en")
        load = time.perf_counter() - t0
        per_pass = []
        for _ in range(spec.get("passes", args.passes)):
            t = time.perf_counter()
            for text in texts:
                engine.analyze(text, language="en")
            per_pass.append(1000 * (time.perf_counter() - t) / len(texts))
        out["systems"][name] = {"load_seconds": round(load, 1),
                                "ms_per_note_median": round(statistics.median(per_pass), 1),
                                "ms_per_note_passes": [round(x, 1) for x in per_pass]}
        print(name, out["systems"][name], flush=True)
        del engine

    with open(RESULTS_DIR / "timing.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
