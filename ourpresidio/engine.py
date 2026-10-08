"""Our clinical de-identification system, built on the PyPI Presidio package.

Nothing in Presidio is modified. Each improvement plugs into one of Presidio's
extension points and can be switched on/off for the ablation study:

  step       gap   extension point
  ---------  ----  -------------------------------------------------------------
  age        G1    custom PatternRecognizer added to the registry
  mrn        G2    custom PatternRecognizer added to the registry
  registry   G4    recognizer-registry YAML (country filter: India)
  hospital   G3    custom PatternRecognizer for facility names
  org        G3    NLP-engine YAML: stop ignoring the NER model's ORGANIZATION
  allow      G5    analyze(allow_list=...) with clinical vocabulary
  post       G5-9  post-processing of RecognizerResults (our wrapper)
  quiet      G11   warning filter so note text never reaches the logs

Usage:
    from ourpresidio.engine import ClinicalAnalyzer
    analyzer = ClinicalAnalyzer(base="lg", steps=ALL_STEPS)
    results = analyzer.analyze(text)
"""

import warnings
from pathlib import Path

import regex as re

from presidio_analyzer import AnalyzerEngineProvider, RecognizerResult

from .clinical_vocab import ALLOW_LIST
from .recognizers import (
    AgeRecognizer,
    FixedInPanRecognizer,
    HospitalNameRecognizer,
    MedicalRecordNumberRecognizer,
)

CONF = Path(__file__).resolve().parent / "conf"
PRESIDIO_CONF = Path(__import__("presidio_analyzer").__file__).resolve().parent / "conf"

ALL_STEPS = ["age", "mrn", "registry", "hospital", "org", "allow", "post", "quiet"]

# NLP config per base model: (default labels, with ORGANIZATION kept)
BASES = {
    "lg": (PRESIDIO_CONF / "default.yaml", CONF / "spacy_lg_org.yaml"),
    "trf": (CONF / "spacy_trf.yaml", CONF / "spacy_trf_org.yaml"),
    "stanford": (PRESIDIO_CONF / "transformers.yaml", CONF / "stanford_fixed.yaml"),
}

TITLE = re.compile(r"^(?:(?:Dr|Mr|Mrs|Ms|Miss|Prof|Sri|Shri|Smt|Baby|Patient|Master)\.?\s+)+")
DURATION = re.compile(
    r"^(?:(?:for|since|over|past|last|about|around|nearly|almost|a|an|the)\s+)*"
    r"(?:\d+(?:\.\d+)?|a\s+few|few|several|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|couple\s+of)\s*(?:-\s*)?"
    r"(?:days?|weeks?|months?|years?|hours?|hrs?|wks?|yrs?)"
    r"(?:\s+(?:back|ago|old|later|earlier))?\.?$",
    re.IGNORECASE,
)


class ClinicalAnalyzer:
    def __init__(self, base="lg", steps=ALL_STEPS):
        unknown = set(steps) - set(ALL_STEPS)
        if unknown:
            raise ValueError(f"unknown steps {unknown}")
        self.base, self.steps = base, list(steps)
        if "quiet" in self.steps:
            # G11: spacy-huggingface-pipelines puts the first ~100 characters of the
            # note (patient name, age, UHID) into this warning. Never let it out.
            warnings.filterwarnings("ignore", message=r"Skipping annotation")

        default_nlp, org_nlp = BASES[base]
        self.engine = AnalyzerEngineProvider(
            nlp_engine_conf_file=str(org_nlp if "org" in self.steps else default_nlp),
            recognizer_registry_conf_file=(
                str(CONF / "registry_india.yaml") if "registry" in self.steps else None
            ),
        ).create_engine()

        if "registry" in self.steps:
            # G14: Presidio's "PAN (Low)" pattern has unbounded lookaheads, so any
            # 10-letter word followed anywhere later by 4 digits becomes a PAN.
            self.engine.registry.remove_recognizer("InPanRecognizer")
            self.engine.registry.add_recognizer(FixedInPanRecognizer())
        if "age" in self.steps:
            self.engine.registry.add_recognizer(AgeRecognizer())
        if "mrn" in self.steps:
            self.engine.registry.add_recognizer(MedicalRecordNumberRecognizer())
        if "hospital" in self.steps:
            self.engine.registry.add_recognizer(HospitalNameRecognizer())

    @property
    def registry(self):
        return self.engine.registry

    def get_supported_entities(self, language="en"):
        return self.engine.get_supported_entities(language)

    def analyze(self, text, language="en"):
        kwargs = {}
        if "allow" in self.steps:
            kwargs.update(allow_list=ALLOW_LIST, allow_list_match="exact")
        results = self.engine.analyze(text=text, language=language, **kwargs)
        if "post" in self.steps:
            results = postprocess(text, results)
        return results


# ---------------------------------------------------------------- post-processing

def _trim(text, r):
    """Cut a span at line breaks (G8), strip titles from names, strip edge punctuation."""
    start, end = r.start, r.end
    seg = text[start:end]
    if "\n" in seg or "\r" in seg:
        # keep the first non-empty line of the span
        offset = 0
        for line in re.split(r"(\r?\n)", seg):
            if line.strip() and line not in ("\n", "\r\n"):
                start, end = start + offset, start + offset + len(line)
                break
            offset += len(line)
    seg = text[start:end]
    if r.entity_type == "PERSON":
        m = TITLE.match(seg)
        if m:
            start += m.end()
    while start < end and text[start] in " \t\r\n,;:.([":
        start += 1
    while end > start and text[end - 1] in " \t\r\n,;:([":
        end -= 1
    return start, end


def _is_false_person(span):
    """A name contains at least one capitalised word (G5: Hinglish/lowercase phrases)."""
    return not re.search(r"\b[A-Z]", span)


def postprocess(text, results):
    out = []
    for r in results:
        start, end = _trim(text, r)
        if start >= end:
            continue
        span = text[start:end]
        if r.entity_type == "DATE_TIME" and DURATION.match(span):
            continue  # G7: a duration ("for 5 days") is not a date
        if r.entity_type == "PERSON" and _is_false_person(span):
            continue
        out.append(RecognizerResult(r.entity_type, start, end, r.score,
                                    analysis_explanation=r.analysis_explanation,
                                    recognition_metadata=r.recognition_metadata))
    return _resolve_overlaps(text, out)


# When two different types claim overlapping text, the more specific one wins.
PRIORITY = {"AGE": 6, "MEDICAL_RECORD_NUMBER": 5, "ORGANIZATION": 4, "PERSON": 3,
            "DATE_TIME": 2, "LOCATION": 1}


ADJACENT_GAP = re.compile(r"^[ \t,]{0,3}$")  # same line: "Jaipur, Rajasthan", "07/02/2026 09:00 AM"


def _merge_same_type(text, results):
    """Same-type results that overlap, or are separated only by a comma/spaces on the
    same line, become one span covering both (max score)."""
    merged = []
    for r in sorted(results, key=lambda r: (r.entity_type, r.start)):
        last = merged[-1] if merged else None
        if last and last.entity_type == r.entity_type and (
            r.start < last.end or ADJACENT_GAP.match(text[last.end:r.start])
        ):
            last.end = max(last.end, r.end)
            last.score = max(last.score, r.score)
        else:
            merged.append(RecognizerResult(r.entity_type, r.start, r.end, r.score,
                                           analysis_explanation=r.analysis_explanation,
                                           recognition_metadata=r.recognition_metadata))
    return merged


def _resolve_overlaps(text, results):
    """G9: one label per stretch of text, without ever losing coverage.

    Same-type overlaps (and comma/space-adjacent spans) are merged. Across types, a result is dropped only when it
    lies entirely inside a higher-priority result (e.g. DATE_TIME "17 years"
    inside AGE "17 years"); partial overlaps are kept so no PHI character is lost.
    """
    ranked = sorted(_merge_same_type(text, results),
                    key=lambda r: (-PRIORITY.get(r.entity_type, 0), -r.score, -(r.end - r.start)))
    kept = []
    for r in ranked:
        if any(k.start <= r.start and r.end <= k.end for k in kept):
            continue
        kept.append(r)
    return sorted(kept, key=lambda r: r.start)
