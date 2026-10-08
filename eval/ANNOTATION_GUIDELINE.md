# Annotation Guideline — PHI in Clinical_text (English notes)

Version 1.0 · applies to `data/Clinical_text/1.txt` … `100.txt`

This guideline defines what counts as Protected Health Information (PHI) in the
gold standard, and exactly where each label starts and ends. Every Presidio run
(baseline and improved) is scored against labels made with these rules.

It is based on the 18 HIPAA Safe Harbor identifiers, adapted to Indian
discharge summaries.

## 1. Label set

| Label | What it covers | Examples from the notes |
|---|---|---|
| `PERSON` | Names of the patient, doctors, relatives, or any other person | `Soumya Das`, `Rajesh Kumar` |
| `AGE` | The patient's age | `8 months`, `17 years`, `45` |
| `DATE_TIME` | Dates and times tied to the patient's care | `07/02/2026 09:00 AM` |
| `ID` | Record numbers that identify the patient or episode | `582614792` (UHID), `ADM-20264745` |
| `LOCATION` | Patient address, locality, city, state | `Jaipur, Rajasthan` |
| `ORGANIZATION` | The treating hospital | `JIPMER Puducherry` |

## 2. Boundary rules

1. **PERSON:** label the name only. Titles and roles are *outside* the span.
   - `Dr. Rajesh Kumar, Neurology` → `Rajesh Kumar`
   - `Dr. Naresh Trehan (Cardiac Surgeon)` → `Naresh Trehan`
   - `Baby Aarav` → `Aarav` (`Baby` is a newborn prefix, not part of the name)
2. **AGE:** number plus unit if a unit is written. The sex marker is not part of the span.
   - `8 months/M` → `8 months`; `17 years/M` → `17 years`; `45/F` → `45`
3. **DATE_TIME:** date and time together form **one** span.
   - `07/02/2026 09:00 AM` → one span (not two).
4. **ID:** the number only, without the field label. The `ADM-` prefix is part of the number.
   - `UHID: 582614792` → `582614792`; `Admission No: ADM-20264745` → `ADM-20264745`
5. **LOCATION:** the whole address value is **one** span, including the comma.
   - `Address: Salt Lake City, Kolkata` → `Salt Lake City, Kolkata`
6. **ORGANIZATION:** the full hospital name as written on line 1, including the city
   that is part of the name. It is one flat span (no nested LOCATION inside).
   - `Max Super Speciality Hospital Delhi` → one span.
7. Field labels (`Patient Name:`, `UHID:` …) are never part of a span.
8. Leading and trailing spaces and punctuation are never part of a span.

## 3. NOT PHI (never labelled)

- Sex (`M`, `F`)
- Diseases, symptoms, findings, ICD codes (`I63.9`, `M51.26`)
- Drugs and doses (`Tab. Clopidogrel 75mg OD`)
- Medical departments and specialties (`Neurology`, `Orthopaedics`, `Cardiac Surgeon`)
- Clinical scales (`Class IV as per modified Kuppuswamy scale`)
- Clinical mnemonics (`PICCKLE`)
- Hinglish phrases (`Patient ko fever tha`)
- Traditional medicine names (`Tulsi`, `Ashwagandha`)
- Durations (`for 4 days`, `20 weeks`)
- Document headings (`Discharge Summary`, `Signature`)

## 4. Design decisions (and why)

| Decision | Reason |
|---|---|
| All ages are PHI, not only ages over 89 (HIPAA's limit) | Combined with the other fields, age helps identify the patient; stricter is safer for a de-identification test. |
| The hospital is PHI (`ORGANIZATION`) | Treating facility plus dates narrows down the patient; also tests Presidio's disabled ORGANIZATION type. |
| The doctor's name is PHI | HIPAA covers the patient's relatives and employers, not providers. We follow the stricter practice (as in the i2b2 2014 de-id corpus) of labelling all person names. |
| Address is one span | It is one field value. Scoring with *overlap* matching still credits a system that finds `Jaipur` and `Rajasthan` separately. |

## 5. Process

1. `eval/make_gold.py` drafts the labels from the template fields and computes
   exact character offsets. It never calls Presidio.
2. A reviewer checks every note and records corrections (missed PHI, wrong
   label, wrong boundary) in `eval/gold/corrections.json`.
3. Corrections are applied, and the result is frozen as `eval/gold/gold.jsonl`.
   It is not changed after the first Presidio run.

### Review actually performed (v1.0, 2026-10-05)

The review was done by Claude (AI assistant), not by a human annotator. Because
the notes share one template, every line of all 100 notes was checked in two
groups:

- **Labelled lines** (249 distinct): each shown with its span bracketed, to
  check label and boundaries.
- **All other lines** (207 distinct, de-duplicated across notes): read in full
  to look for PHI the draft missed.

Result: one systematic correction. In 8 notes the patient name was written
`Baby Aarav` / `Baby Priya`; the span was narrowed to the name (rule 1). No
missed PHI was found. Final gold standard: 1,000 spans.

**Limitation to report:** no human annotator and no inter-annotator agreement.
A human spot-check of a random sample (e.g. 10 notes on `review.html`) would
strengthen this.

## 6. Offsets

Offsets are character positions in the file text exactly as stored on disk
(UTF-8, Windows `\r\n` line endings preserved). `text[start:end]` must equal
the `text` field of the label. All scripts read notes through `eval/common.py`
so that the gold standard and Presidio see identical strings.
