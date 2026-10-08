"""Custom Presidio recognizers for clinical notes (gaps G1, G2, G3).

All three are plain `PatternRecognizer`s, the extension point Presidio provides
for rule-based detection. Patterns are written to be general (any clinical
note), not tied to the Clinical_text template: e.g. the age rule also handles
"a 45-year-old woman" and "aged 6 months", which never occur in the template.

Presidio compiles patterns with the `regex` package, which allows
variable-length lookbehind; we use it so that a field label like "Age:" or
"UHID:" acts as required context without becoming part of the span.
"""

import regex as re

from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.predefined_recognizers import InPanRecognizer

UNIT = r"(?:years?|yrs?|months?|mos?|weeks?|wks?|days?)"

# Case-insensitive, but no DOTALL: a match must never cross a line break.
CI = re.IGNORECASE | re.MULTILINE
# Case-sensitive, for rules that rely on capitalised words.
CS = re.MULTILINE


class AgeRecognizer(PatternRecognizer):
    """G1: patient age. Presidio has no AGE recognizer."""

    PATTERNS = [
        # "45-year-old", "6 month old", "3 weeks-old"
        Pattern("age_n_unit_old", rf"\b\d{{1,3}}[ -]?{UNIT}[ -]old\b", 0.85),
        # "Age: 45", "Age/Sex: 45/M", "aged 8 months", "age of 62 years"
        Pattern(
            "age_after_label",
            rf"(?<=\bage[sd]?\b(?:/sex)?[ \t:.,-]{{0,4}}(?:of[ \t]+)?)\d{{1,3}}(?:[ \t]?{UNIT})?\b",
            0.85,
        ),
        # "45 y/o", "45yo", "45 yrs old"
        Pattern("age_yo", r"\b\d{1,3}[ \t]?(?:y/?o|yrs?[ \t]old)\b", 0.85),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="AGE",
            name="AgeRecognizer",
            patterns=self.PATTERNS,
            context=["age", "aged", "old", "year-old"],
            global_regex_flags=CI,
        )


class MedicalRecordNumberRecognizer(PatternRecognizer):
    """G2: hospital record numbers (UHID, MRN, IP/OP/CR/registration/admission no.)."""

    LABEL = (
        r"(?:UHID|MRN|MR[ \t]?No|CR[ \t]?No|IP[ \t]?No|OP[ \t]?No|IPD[ \t]?No|OPD[ \t]?No"
        r"|Reg(?:istration)?[ \t]?No|Admission[ \t]?No|Adm[ \t]?No|Hospital[ \t]?No"
        r"|Patient[ \t]?ID|Record[ \t]?No|Medical[ \t]Record[ \t]No)"
    )
    PATTERNS = [
        # Number right after a record label: "UHID: 582614792", "Admission No: ADM-20264745"
        Pattern(
            "mrn_after_label",
            rf"(?<=\b{LABEL}\.?[ \t]*[:#.-]?[ \t]*)[A-Z]{{0,4}}[-/]?(?:\d{{2,4}}/)?\d{{4,12}}\b",
            0.85,
        ),
        # Prefixed record codes anywhere: "ADM-20264745", "IP/2023/004512", "MRN12345678"
        Pattern("mrn_prefixed", r"\b(?:ADM|IPD?|OPD?|MRN|UHID|REG|CR)[-/]?(?:\d{2,4}/)?\d{5,12}\b", 0.6),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="MEDICAL_RECORD_NUMBER",
            name="MedicalRecordNumberRecognizer",
            patterns=self.PATTERNS,
            context=["uhid", "mrn", "record", "admission", "registration", "ipd", "opd"],
            global_regex_flags=CI,
        )


class HospitalNameRecognizer(PatternRecognizer):
    """G3: hospital / facility names (Presidio drops ORGANIZATION by default)."""

    KEYWORD = (
        r"(?:Hospitals?|Medical[ \t]College(?:[ \t]and[ \t]Hospital)?|Medical[ \t]Cent(?:re|er)"
        r"|Institute[ \t]of[ \t]Medical[ \t]Sciences|Nursing[ \t]Home|Health[ \t]?[Cc]are|Medicity"
        r"|Clinic|Infirmary|Sanatorium)"
    )
    # Well-known Indian institute acronyms (gazetteer, documented in the report).
    ACRONYM = r"(?:AIIMS|PGIMER|JIPMER|NIMHANS|SGPGI|SGPGIMS|KGMU|CMC|KEM|ESIC|BHU|IGIMS|SCTIMST|RIMS)"
    CAP = r"[A-Z][A-Za-z&.'-]*"  # a capitalised word
    PATTERNS = [
        # 1-5 capitalised words + keyword + up to 2 capitalised words (usually the city)
        Pattern(
            "hospital_keyword",
            rf"\b(?:{CAP}[ \t]+){{1,5}}{KEYWORD}\b(?:[ \t]+{CAP}){{0,2}}",
            0.7,
        ),
        # Institute acronym + optional city: "AIIMS Delhi", "PGIMER Chandigarh"
        Pattern("hospital_acronym", rf"\b{ACRONYM}\b(?:[ \t]+{CAP}){{0,2}}", 0.7),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="ORGANIZATION",
            name="HospitalNameRecognizer",
            patterns=self.PATTERNS,
            context=["hospital", "admitted", "discharged", "referred", "transferred"],
            global_regex_flags=CS,
        )


class FixedInPanRecognizer(InPanRecognizer):
    """G14: Presidio's Indian PAN recognizer with the "PAN (Low)" pattern bounded.

    The shipped low pattern is
        \b((?=.*?[a-zA-Z])(?=.*?[0-9]{4})[\w@#$%^?~-]{10})\b
    and its lookaheads scan the rest of the text, so "Chandigarh. Discharged 2026"
    yields two PANs. Here both lookaheads are limited to the 10-character token.
    High and medium patterns are unchanged.
    """

    def __init__(self):
        shipped = InPanRecognizer.PATTERNS
        low = Pattern(
            "PAN (Low, bounded)",
            r"\b((?=[\w@#$%^?~-]{0,9}[a-zA-Z])(?=[\w@#$%^?~-]{0,6}[0-9]{4})[\w@#$%^?~-]{10})\b",
            0.01,
        )
        super().__init__(patterns=[p for p in shipped if p.name != "PAN (Low)"] + [low])
