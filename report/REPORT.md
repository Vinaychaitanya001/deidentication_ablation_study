# Evaluating Microsoft Presidio on Clinical Discharge Summaries

**Independent study · running report** · last updated 2026-10-06

This file is the single record of what has been done, how, and what was found.
It is updated after every step. The newest entry in the [change log](#11-change-log)
says where the work currently stands.

---

## Status at a glance

| Phase | What | Status |
|---|---|---|
| 0 | Setup: verify repository, install package and model | ✅ Done |
| 1 | Gold standard (correct answers) for 100 English notes | ✅ Done, frozen |
| 2 | Baseline: Presidio exactly as shipped | ✅ Done (dev split) |
| 3 | Compare Presidio's other shipped configurations | ✅ Done (4 configs on dev) |
| 4 | Gap analysis mapped to Presidio's architecture | ✅ Done (G1–G14) |
| 5 | Improvements as plug-ins, one at a time | ✅ Done: ablations on 3 bases; final systems chosen on dev |
| 6 | Final evaluation on held-out test notes (51–100) | ✅ Done: scored once; speed re-measured on idle machine |
| — | German notes (62 GraSCCo letters) | ⬜ Later phase |

### Key results (held-out test notes 51–100, 500 PHI items)

| System | F1 (any type) | F1 (typed) | F1 (exact span) | PHI missed | False alarms | PHI characters left visible | Speed (CPU) |
|---|---|---|---|---|---|---|---|
| Presidio default, as shipped | 0.777 | 0.738 | 0.392 | 82 | 288 | 23.4% | 38 ms/note |
| **Ours-fast** (same model + our plug-ins) | **0.993** | **0.979** | **0.951** | **2** | **5** | **2.2%** | 45 ms/note |
| **Ours-accurate** (transformer model + plug-ins) | **1.000** | **0.980** | **0.963** | **0** | **0** | **0.5%** | 596 ms/note |

1. **Baseline.** Out of the box, Presidio misses all ages and all hospital names.
   It finds hospital IDs only by accident, through US-format recognizers at
   0.01–0.05 confidence. It also raises 288 false alarms on Hinglish phrases,
   clinical terms, durations and ICD codes.
2. **Presidio's other shipped models** (Phase 3) each fix some gaps but not
   others. The best, `en_core_web_trf`, reaches F1 0.91 at about 15× the run time.
3. **Our plug-ins** use only Presidio's own extension points. They close the
   gaps with the *same* default model and at the same speed. On the test set:
   - F1 rises from 0.777 to 0.993;
   - missed PHI falls from 82 to 2;
   - false alarms fall from 288 to 5.
4. **Test results match dev** (within ±0.01), so there was no overfitting to the
   development notes. All 100 notes share one template, though, so performance
   on differently formatted notes is not shown here (Limitations, Section 8).
5. **Presidio issues found:** 14 gaps (G1–G14), including:
   - a bug in the Indian PAN recognizer (G14);
   - a documented config option the validator rejects (G13);
   - patient text written to logs by the transformer pipeline (G11).

---

## 1. Objective

1. Measure how well the official **Presidio** package (PyPI) detects protected
   health information (PHI) in the `Clinical_text` discharge summaries.
2. Find where it fails, and which part of Presidio's architecture is responsible.
3. Improve it through Presidio's own extension points, without modifying its code.
4. Show the improvement on notes that were never used for tuning.

## 2. Setup

### 2.1 Repository check

The local copy `presidio-main/` (from `presidio.zip`) was compared file by file
against GitHub `microsoft/presidio` (`main`, commit `d884790`, 2026-10-04) using
git content hashes.

| | Count |
|---|---|
| Files on GitHub | 918 |
| Files in local copy | 917 |
| Byte-identical | 914 |
| Different content | 3 (`docs/index.md`, `docs/project_transition.md`, `presidio-structured/.../data_reader.py`) |
| Missing locally | 1 (`presidio-structured/tests/test_data_reader.py`) |

The local copy is an exact snapshot of commit `d4ccc6b` (2026-09-29). All four
differences come from two later commits (docs, and a presidio-structured CSV/JSON
feature). **presidio-analyzer, the package under test, is identical.**

### 2.2 What is tested

The **PyPI package**, not the local source. `presidio-main/` is used only as
reading material for the architecture (it is not included in this repository).

| Component | Version | Source |
|---|---|---|
| Python | 3.14.0 | |
| presidio-analyzer | 2.2.364 (latest on PyPI) | PyPI via pip |
| presidio-anonymizer | 2.2.364 | PyPI via pip |
| spaCy | 3.8.16 | PyPI |
| en_core_web_lg | 3.8.0 | spaCy GitHub release |
| en_core_web_sm, en_core_web_trf | 3.8.0 | spaCy GitHub release (Phase 3+) |
| torch / transformers / gliner | 2.14.1 (CPU) / 4.57.6 / 0.2.29 | PyPI, via `presidio-analyzer[transformers,gliner]` (Phase 3+) |
| Hugging Face models | `StanfordAIMI/stanford-deidentifier-base`, `urchade/gliner_multi_pii-v1` | Hugging Face Hub (Phase 3+) |

### 2.3 What "default Presidio" means

`AnalyzerEngine()` with no arguments loads, from the package's own config files:

- **NLP engine:** spaCy `en_core_web_lg`, a general English model trained on web and news text (not clinical).
  It reports PERSON, LOCATION, DATE_TIME and NRP. **ORGANIZATION is in `labels_to_ignore`.**
- **Rule-based recognizers (on):** dates, email, phone, URL, IP, IBAN, credit card, crypto, MAC,
  US medical licence, US SSN / passport / driver licence / bank / ITIN, UK NHS.
- **Off by default:** all Indian recognizers (Aadhaar, PAN, passport, voter ID, vehicle, GSTIN),
  all German recognizers, and the Hugging Face transformer recognizer.
- **No recognizer exists** for age or hospital record numbers (UHID, admission number).
- Context enhancement: `LemmaContextAwareEnhancer`. Score threshold: 0 (everything is returned).

## 3. Data

`Clinical_text.zip` holds 162 files:

| Part | Files | Description |
|---|---|---|
| English | 100 (`1.txt`–`100.txt`) | Synthetic Indian hospital discharge summaries, one template, ~1.1 KB each. Hinglish phrases in history ("Patient ko dard tha"). |
| German | 62 (`Albers.txt`, `Colon_Fake_A.txt`, …) | Free-text German discharge letters; filenames match the public GraSCCo corpus. Deferred to a later phase. |

The notes come **without labels**, so a gold standard had to be built (Section 4).

Because all English notes share one template, a rule like "whatever follows
`Patient Name:` is a name" would score almost perfectly here and prove nothing.
This is why improvements are developed on notes 1–50 only and judged on 51–100.

## 4. Method

### 4.1 Gold standard

Full rules: [`eval/ANNOTATION_GUIDELINE.md`](../eval/ANNOTATION_GUIDELINE.md).

| Label | Covers | Example |
|---|---|---|
| PERSON | patient, doctors | `Soumya Das` (without `Dr.`, `Baby`, or role) |
| AGE | patient age | `8 months`, `17 years`, `45` |
| DATE_TIME | admission/discharge date+time, one span | `07/02/2026 09:00 AM` |
| ID | UHID, admission number | `582614792`, `ADM-20264745` |
| LOCATION | address, one span | `Jaipur, Rajasthan` |
| ORGANIZATION | hospital name | `JIPMER Puducherry` |

Not PHI: sex, diseases, ICD codes, drugs, departments, durations ("for 4 days"),
clinical scales, Hinglish phrases.

**Process**

1. `eval/make_gold.py` drafted labels from the template fields with exact character
   offsets. It never calls Presidio, so the answers are independent of the system under test.
2. Every line of all 100 notes was reviewed: 249 distinct labelled lines (checked
   label and boundaries) and 207 distinct unlabelled lines (checked for missed PHI).
3. One systematic correction: in 8 notes `Baby Aarav` / `Baby Priya` → `Aarav` / `Priya`.
   No missed PHI was found.
4. Frozen as `eval/gold/gold.jsonl`: **1,000 spans** (300 PERSON, 200 DATE_TIME,
   200 ID, 100 AGE, 100 LOCATION, 100 ORGANIZATION).

**Limitation:** the review was done by the AI assistant, not a human annotator,
and there is no inter-annotator agreement. A human spot-check of ~10 notes on
`eval/gold/review.html` (regenerate with `eval/make_gold.py`) would strengthen this.

### 4.2 Data split

| Split | Notes | Use |
|---|---|---|
| dev | 1–50 | finding gaps, building and tuning improvements |
| test | 51–100 | **held out**; scored only once, in the final evaluation |

### 4.3 Running Presidio

`eval/run_clinical.py` runs the analyzer on each note exactly as stored on disk
(UTF-8, Windows `\r\n` line endings), and saves every detection with its type,
offsets, confidence score and the recognizer that produced it.

### 4.4 Scoring

`eval/score.py` compares detections with the gold standard under three rules:

| Rule | A detection matches a gold span when… | Question it answers |
|---|---|---|
| strict | same type and identical start/end | Is the span exactly right? |
| overlap | same type and the spans overlap | Is the PHI found with the right type? |
| any | the spans overlap, type ignored | Would this PHI be hidden by redaction? |

- **Precision** = matched detections / all detections.
- **Recall** = matched gold spans / all gold spans. This matters most: a miss is a privacy leak.
- **F1** = harmonic mean of precision and recall.
- **PHI character recall** = share of PHI characters covered by any detection.

Presidio's US identifier types (SSN, passport, driver licence, bank, ITIN, NHS,
medical licence) count as `ID`.

The scorer was checked on two synthetic runs with known answers (perfect, and
deliberately broken) and reproduced the expected numbers exactly.

## 5. Results: baseline (dev notes 1–50)

Presidio 2.2.364 + `en_core_web_lg` 3.8.0, default settings. **42 ms per note**
(model load 11.8 s). 1,051 detections against 500 gold spans.

### 5.1 Overall

| Rule | Precision | Recall | F1 |
|---|---|---|---|
| strict | 0.351 | 0.442 | 0.391 |
| overlap | 0.680 | 0.780 | 0.727 |
| any | 0.726 | 0.848 | 0.782 |

PHI characters covered: 5,451 / 7,365 = **0.740**. 26% of PHI characters would leak.

### 5.2 Per type

| Type | Strict P / R | Overlap P / R / F1 | Recall (any) |
|---|---|---|---|
| PERSON | 0.36 / 0.75 | 0.47 / 0.97 / 0.63 | 0.97 |
| DATE_TIME | 0.20 / 0.59 | 0.67 / 1.00 / 0.80 | 1.00 |
| ID | 0.55 / 0.50 | 0.83 / 1.00 / 0.91 | 1.00 |
| LOCATION | 0.00 / 0.00 | 0.88 / 0.90 / 0.89 | 1.00 |
| AGE | – / 0.00 | – / 0.00 / 0.00 | 0.48 |
| ORGANIZATION | – / 0.00 | – / 0.00 / 0.00 | 0.10 |

### 5.3 The ID result is luck

Every UHID and admission number was matched **only** by US recognizers at very
low confidence. The same 9-digit UHID is reported up to four times, under four
different US types:

| Gold field | Matched by | Confidence |
|---|---|---|
| UHID (9 digits) | UsSsn, UsPassport, UsBank, UsLicense | 0.01–0.05 |
| Admission no. `ADM-…` | UsBank, UsLicense (digits only, never the full span) | 0.01–0.05 |

### 5.4 Threshold sweep

| Threshold | Any P / R / F1 | Overlap P / R / F1 |
|---|---|---|
| 0.0 (default) | 0.726 / 0.848 / 0.782 | 0.680 / 0.780 / 0.727 |
| 0.1–0.3 | 0.618 / 0.660 / 0.638 | 0.554 / 0.580 / 0.567 |
| 0.4–0.85 | 0.673 / 0.660 / 0.666 | 0.604 / 0.580 / 0.592 |
| ≥ 0.9 | 1.000 / 0.200 / 0.333 | 1.000 / 0.200 / 0.333 |

Scores come in only three groups: 0.01–0.05 (US regexes), 0.85 (spaCy) and
0.95 (date regex). No threshold improves on the default, and any threshold ≥ 0.1
removes every ID.

### 5.5 Errors

**Missed PHI (110 gold spans, overlap rule)**

| What | Missed | Of which still hidden under another type |
|---|---|---|
| Hospital (ORGANIZATION) | 50 | 5 (as LOCATION) |
| Age | 50 | 24 (as DATE_TIME) |
| Address (LOCATION) | 5 | 5 (as PERSON) |
| Patient name | 5 | 0 (`Soumya Das`, `Gursharan Singh` ×4) |

**False alarms (336 detections)**: 48 are real PHI labelled with the wrong type.
The other **288 touch no PHI at all**:

| Category | Count | Examples |
|---|---|---|
| Medical term / herb / department as PERSON | 83 | `Koilonychia` (50, every note), `Tulsi` 14, `Neurology` 9, `Viral Exanthem`, `Cachexic` |
| Duration as DATE_TIME | 71 | `5 days`, `2 weeks`, `a few years back` |
| Hinglish phrase as PERSON | 67 | `ko dard tha`, `kar raha tha`, `aur bolne mein` |
| ICD code / spine level as US driver licence | 62 | `C50`, `J18`, `M17`, `L4`, `L5` |
| Body region as LOCATION | 5 | `Epigastric` |

**Boundary errors.** spaCy often extends a name over the line break into the next
field label, e.g. `Aman Verma\r\nAge`, `Rajesh Kumar\r\nSignature` (28 PERSON
spans in dev). These are found under overlap, but fail strict matching.

### 5.6 Side experiment: line endings

Same notes, Windows (`\r\n`) vs Unix (`\n`) line endings, PERSON only:

| Line endings | Exact PERSON matches | Spans crossing a line break | Names missed entirely |
|---|---|---|---|
| `\r\n` (as stored) | 112 / 150 | 28 | 5 (`Soumya Das`, `Gursharan Singh` ×4) |
| `\n` | 103 / 150 | 41 | 1 (`Soumya Das`) |

Line endings are not the cause of the line-crossing problem, but they **change
which names are found**. Presidio's output depends on how the text file was saved.

## 5b. Phase 3: Presidio's other shipped configurations (dev notes 1–50)

Same notes, same gold standard, same scorer. Only the NLP model / analyzer
configuration changes, and each comes from Presidio itself:

| Run | Configuration | Model(s) | Source |
|---|---|---|---|
| A (baseline) | `default.yaml` | spaCy `en_core_web_lg` (general English, CNN) | Presidio default |
| B | `default.yaml` with model swapped | spaCy `en_core_web_sm` (small CNN) | Presidio docs: change `model_name` |
| C | `default.yaml` with model swapped | spaCy `en_core_web_trf` (RoBERTa transformer) | Presidio docs: change `model_name` |
| D | `transformers.yaml` (shipped) | `StanfordAIMI/stanford-deidentifier-base` (clinical de-id transformer) + `en_core_web_sm` for tokens | Presidio conf, unchanged |
| E | `slim.yaml` (shipped) | GLiNER `urchade/gliner_multi_pii-v1` (zero-shot PII model) replacing spaCy NER | Presidio conf, unchanged |

Extra packages installed for this phase, through Presidio's own optional extras
(`presidio-analyzer[transformers,gliner]`): torch 2.14.1 (CPU), transformers 4.57.6,
spacy-huggingface-pipelines 0.0.4, gliner 0.2.29, onnxruntime 1.30.0.

**Control check.** The comparison runs load Presidio through `AnalyzerEngineProvider`
with a YAML file, while the baseline used `AnalyzerEngine()`. Running the default
config through the provider gave **identical** detections (2,102 / 2,102), so any
difference below comes from the model, not from how Presidio was loaded.

**Config observations (before running)**

- `transformers.yaml` maps the Stanford model's `HOSPITAL` label to `LOCATION`, not
  `ORGANIZATION`, and multiplies `ID` scores by 0.4 (`low_score_entity_names`).
- `slim.yaml` removes spaCy NER entirely; GLiNER is prompted with Presidio's default
  label names (`PERSON`, `HOSPITAL`, `AGE`, `ID`, …) at threshold 0.30.

### Results

Best value in each column in **bold**.

| Run | Any P / R / F1 | Overlap P / R / F1 | Strict F1 | PHI chars covered | Detections | ms/note* |
|---|---|---|---|---|---|---|
| A `en_core_web_lg` (baseline) | 0.726 / 0.848 / 0.782 | 0.680 / 0.780 / 0.727 | 0.391 | 0.740 | 1051 | **42** |
| B `en_core_web_sm` | 0.600 / 0.826 / 0.695 | 0.542 / 0.720 / 0.618 | 0.280 | 0.704 | 1198 | **40** |
| C `en_core_web_trf` | 0.862 / 0.954 / **0.905** | 0.771 / 0.794 / 0.782 | **0.518** | 0.812 | 960 | 651 |
| D Stanford de-id | **0.878** / 0.900 / 0.889 | **0.796** / 0.800 / **0.798** | 0.395 | 0.841 | **882** | 359 |
| E GLiNER | 0.525 / **0.938** / 0.673 | 0.525 / **0.938** / 0.673 | 0.259 | **0.868** | 1461 | 2928 |

Per type: overlap F1, with recall under the `any` rule in brackets.

| Run | PERSON | AGE | DATE_TIME | ID | LOCATION | ORGANIZATION |
|---|---|---|---|---|---|---|
| A baseline (`lg`) | 0.63 (0.97) | 0.00 (0.48) | 0.80 (1.00) | 0.91 (1.00) | 0.89 (1.00) | 0.00 (0.10) |
| B `sm` | 0.45 (0.94) | 0.00 (0.48) | 0.79 (1.00) | 0.91 (1.00) | 0.48 (0.66) | 0.00 (0.30) |
| C `trf` | **0.95** (0.98) | 0.00 (0.90) | 0.78 (1.00) | 0.91 (1.00) | 0.87 (1.00) | 0.00 (0.70) |
| D Stanford | 0.90 (1.00) | 0.00 (0.00) | **1.00** (1.00) | 0.89 (1.00) | 0.68 (1.00) | 0.00 (1.00) |
| E GLiNER | 0.50 (1.00) | **0.99** (1.00) | 0.88 (1.00) | 0.87 (1.00) | 0.54 (0.38) | 0.30 (1.00) |

\* Timings in this table were measured while downloads were running in the
background. For reliable speeds, use the idle-machine table in Section 5d:
baseline 38 ms, `trf` 608 ms (16×), Stanford 305 ms (8×), GLiNER 2,127 ms (55×) per note.

### What each configuration does well and badly

**B: `en_core_web_sm` (small CNN).** Worse than the default on every rule:
470 PERSON detections for 150 names (precision 0.30), location recall 0.42,
35 spurious NRP. The default `lg` model is the better of the two CNN options.

**C: `en_core_web_trf` (transformer spaCy).** Best overall F1 (0.905).
PERSON precision jumps from 0.47 to 0.91: the Hinglish and medical-term false
names (`ko dard tha`, `Koilonychia`, `Tulsi`) disappear. Remaining gaps:
- It recognises hospitals as `ORG`, but Presidio throws `ORGANIZATION` away
  (G3), so hospitals are only partly hidden through a city name (35 of 50).
- Ages are still typed DATE_TIME (45 of 50), never AGE (G1).
- Durations still tagged DATE_TIME; ICD codes still flagged as US driver
  licences (G4, G7). IDs still found only by the US regexes.

**D: Stanford de-identifier (`transformers.yaml`).** Best typed F1 (0.798),
fewest detections, and DATE_TIME is perfect (F1 1.00: durations are no longer
tagged). It is the only model that finds UHIDs and admission numbers **itself**
(not via US regexes), so ID recall holds at thresholds up to 0.4. Remaining gaps:
- **AGE recall 0.00, even under `any`.** The model has no AGE label at all
  (its labels: VENDOR, DATE, HCW, HOSPITAL, ID, PATIENT, PHONE). `transformers.yaml`
  maps an `AGE` label the model never emits.
- It finds all 50 hospitals, but `transformers.yaml` maps `HOSPITAL → LOCATION`,
  so they score as wrong-type and LOCATION precision falls to 0.52 (G12).
  *Correction (Phase 5):* this mapping is a deliberate trade-off, not a mistake.
  The Stanford model has **no location label**; it uses `HOSPITAL` for hospitals,
  addresses and cities alike. Mapping it to ORGANIZATION instead (our `org` step)
  turned every address into an ORGANIZATION and LOCATION F1 fell to 0.00. The model
  simply cannot tell a hospital from an address.
- Names include the title (`Dr. Rajesh Kumar`), so strict F1 stays low (0.395);
  ICD codes with a dot (`C50.9`, `J18.9`) are tagged ID.
- **Privacy issue:** when a predicted span cannot be aligned to tokens, the
  `spacy-huggingface-pipelines` library prints a warning that contains the first
  ~100 characters of the note, i.e. the patient's name, age and UHID, to the
  console/log (G11).

**E: GLiNER (`slim.yaml`).** Highest recall (0.938) and PHI-character coverage
(0.868); the **only configuration that detects ages** (AGE F1 0.99) and that
reports hospitals as ORGANIZATION. But:
- Precision is the lowest (0.525). It tags generic words as PHI: `Patient` as
  PERSON (68), `Hospital` as ORGANIZATION (50), and the PICCKLE examination signs
  (`Edema`, `Lymphadenopathy`, `Koilonychia`, `Icterus`, `Clubbing`, `Pallor`)
  as PERSON or ORGANIZATION; departments (`Neurology`, `Pediatrics`) as ORGANIZATION.
- It misses Indian addresses: 31 of 50 (`Anna Nagar, Chennai`, `Moga, Punjab`)
  are not hidden at all.
- `slim.yaml` turns all US recognizers back on, so the ICD-code false alarms remain.
- 2.9 s per note on CPU.

### What Phase 3 means for Phase 5

| Gap | Fixed by a shipped config? |
|---|---|
| G1 Age | Only GLiNER, at very low precision and 70× cost → needs our own recognizer |
| G2 Hospital IDs | Only Stanford (model-level) → own recognizer is cheaper and calibrated |
| G3 Hospital names | trf and Stanford *find* them but config drops/mislabels them → config fix |
| G4 US recognizers on ICD codes | No config fixes it → registry change |
| G5–G6 False / missed names | trf and Stanford largely fix it → model choice |
| G7 Durations as dates | Stanford fixes it; spaCy models do not |
| G8 Line-crossing spans | trf reduces it; Stanford adds titles to names |

The most promising base for Phase 5 is **trf** (best F1, best names) or
**Stanford** (best dates and IDs), with our own recognizers and registry
changes for the gaps no model closes.

## 5c. Phase 5: our system (improvements as Presidio plug-ins)

Code: [`ourpresidio/`](../ourpresidio/). Presidio itself is not modified; every
change uses an extension point Presidio provides.

| Step | Gap | What it does | Presidio extension point | File |
|---|---|---|---|---|
| `age` | G1 | Age after an age label (`Age: 45`, `Age/Sex: 8 months/M`, `aged 62`), `45-year-old`, `70 y/o` | custom `PatternRecognizer` | `recognizers.py` |
| `mrn` | G2 | Record numbers after a record label (UHID, MRN, IP/OP/CR/registration/admission no.), and prefixed codes (`ADM-…`, `IP/2023/…`) | custom `PatternRecognizer` | `recognizers.py` |
| `registry` | G4, G14 | Recognizers of other countries off, Indian on; Presidio's PAN recognizer replaced by a bug-fixed one | registry YAML + `registry.remove/add_recognizer` | `conf/registry_india.yaml` |
| `hospital` | G3 | Capitalised words + facility keyword (`… Hospital`, `Medical College`, `Medicity`, …) + city; Indian institute acronyms (AIIMS, PGIMER, JIPMER, …) | custom `PatternRecognizer` | `recognizers.py` |
| `org` | G3, G12 | Keep the NER model's ORGANIZATION; Stanford `HOSPITAL → ORGANIZATION` | NLP-engine YAML | `conf/*_org.yaml`, `stanford_fixed.yaml` |
| `allow` | G5 | Clinical words that are never PHI: exam signs, specialties, roles, document words, Indian remedies, body regions | `analyze(allow_list=…)` | `clinical_vocab.py` |
| `post` | G5, G7, G8, G9 | Cut spans at line breaks; strip titles (`Dr.`, `Baby`, `Patient`); drop pure durations from DATE_TIME; drop PERSON spans with no capital letter (Hinglish); merge same-type spans that overlap or touch (`Jaipur, Rajasthan`); a span fully inside a more specific one is dropped | wrapper around `analyze()` | `engine.py` |
| `quiet` | G11 | Filter the warning that carries note text | Python `warnings` filter | `engine.py` |

**Guarding against overfitting to the template.**

- No rule refers to a field of this template ("whatever follows `Patient Name:`").
- Every recognizer was unit-tested on sentences that never occur in the notes:
  `a 45-year-old woman`, `aged 6 months`, `IP No. 2023/4512`,
  `transferred to Christian Medical College Vellore`.
- It was also tested on near-misses that must **not** match: `stage 4`,
  `page 12`, `Power: 4/5`, `ICD: I63.9`, `L4-L5`, `Course in Hospital`.
- The allow-list categories were chosen from dev errors but filled with general
  clinical vocabulary.
- The hospital acronym list is a small Indian gazetteer. Because the test notes
  use the same 10 hospitals, the hospital result on the test split will be
  optimistic; this is stated as a limitation.

### Findings while building the system

- **G13: documented option rejected.** Comments in Presidio's own
  `default_recognizers.yaml` / `example_recognizers.yaml` describe a
  `supported_countries` field. The configuration validator in 2.2.364 rejects
  it ("Extra inputs are not permitted"). Workaround: per-recognizer `enabled` flags.
- **G14: PAN recognizer bug.** The "PAN (Low)" pattern
  `\b((?=.*?[a-zA-Z])(?=.*?[0-9]{4})[\w@#$%^?~-]{10})\b` has unbounded
  lookaheads: any 10-letter word followed *anywhere later in the text* by four
  digits is reported as an Indian PAN. Minimal reproduction: in
  `"Treated at Chandigarh. Discharged 2026."`, both `Chandigarh` and `Discharged`
  are returned as `IN_PAN`. On the dev notes, enabling Indian recognizers made
  58 hospital/city words "PAN" numbers, which falsely improved hospital coverage
  from 10% to 62%. Fix: bound both lookaheads to the 10-character token
  (`FixedInPanRecognizer`). A real PAN (`ABCPE1234F`) is still detected.
- **Import cost.** Once the `[transformers]` extra is installed, `import
  presidio_analyzer` takes ≈20–30 s on this laptop (29 s measured with
  `python -X importtime`), even for a spaCy-only pipeline. Presidio's
  transformers module imports torch at import time.
- **Two bugs in our own first version, found by the ablation:**
  - Overlap resolution kept the higher-scoring span and dropped a longer one, so
    `14/02/2026 02:00 PM` lost its time. It now merges same-type spans and never
    removes coverage.
  - Turning on the NER model's ORGANIZATION with `lg` added false organizations
    (`ICD`, `Kuppuswamy`, `Physical Examination: Cranial nerves`). This step is
    kept only where the ablation shows it helps.

### Ablation results: base model `en_core_web_lg` (dev notes 1–50)

Each row adds one step to the row above (cumulative). Row 0 runs our wrapper with
no steps and reproduces the baseline exactly, which checks the wrapper itself.

| # | Step added | Any P / R / F1 | Overlap P / R / F1 | Strict F1 | PHI chars covered | Detections |
|---|---|---|---|---|---|---|
| – | baseline (`AnalyzerEngine()`) | 0.726 / 0.848 / 0.782 | 0.680 / 0.780 / 0.727 | 0.391 | 0.740 | 1051 |
| 0 | none (wrapper only) | 0.726 / 0.848 / 0.782 | 0.680 / 0.780 / 0.727 | 0.391 | 0.740 | 1051 |
| 1 | + `age` | 0.738 / 0.900 / 0.811 | 0.695 / 0.880 / 0.776 | 0.447 | 0.747 | 1101 |
| 2 | + `mrn` | 0.760 / 0.900 / 0.824 | 0.720 / 0.880 / 0.792 | 0.517 | 0.773 | 1201 |
| 3 | + `registry` | 0.731 / 0.900 / 0.807 | 0.674 / 0.880 / 0.763 | 0.479 | 0.773 | 841 |
| 4 | + `hospital` | 0.746 / 0.990 / 0.851 | 0.693 / 0.980 / 0.811 | 0.533 | 0.938 | 891 |
| 5 | + `org` | 0.598 / 0.990 / 0.746 | 0.544 / 0.980 / 0.699 | 0.451 | 0.960 | 1144 |
| 6 | + `allow` | 0.677 / 0.990 / 0.804 | 0.615 / 0.980 / 0.756 | 0.491 | 0.960 | 1011 |
| 7 | + `post` | 0.734 / 0.990 / 0.843 | 0.696 / 0.980 / 0.814 | 0.765 | 0.971 | 710 |
| 8 | + `quiet` | 0.734 / 0.990 / 0.843 | 0.696 / 0.980 / 0.814 | 0.765 | 0.971 | 710 |
| **F** | **all except `org`** | **0.990 / 0.990 / 0.990** | **0.965 / 0.980 / 0.972** | **0.915** | 0.949 | 512 |

Per type (overlap F1, `any` recall in brackets):

| # | PERSON | AGE | DATE_TIME | ID | LOCATION | ORGANIZATION |
|---|---|---|---|---|---|---|
| baseline | 0.63 (0.97) | 0.00 (0.48) | 0.80 (1.00) | 0.91 (1.00) | 0.89 (1.00) | 0.00 (0.10) |
| 1 + age | 0.63 (0.97) | **1.00** (1.00) | 0.80 (1.00) | 0.91 (1.00) | 0.89 (1.00) | 0.00 (0.10) |
| 2 + mrn | 0.63 (0.97) | 1.00 (1.00) | 0.80 (1.00) | 0.93 (1.00) | 0.89 (1.00) | 0.00 (0.10) |
| 3 + registry | 0.63 (0.97) | 1.00 (1.00) | 0.80 (1.00) | **1.00** (1.00) | 0.89 (1.00) | 0.00 (0.10) |
| 4 + hospital | 0.63 (0.97) | 1.00 (1.00) | 0.80 (1.00) | 1.00 (1.00) | 0.89 (1.00) | **1.00** (1.00) |
| 5 + org | 0.63 (0.97) | 1.00 (1.00) | 0.80 (1.00) | 1.00 (1.00) | 0.89 (1.00) | 0.31 (1.00) |
| 6 + allow | 0.76 (0.97) | 1.00 (1.00) | 0.80 (1.00) | 1.00 (1.00) | 0.92 (1.00) | 0.36 (1.00) |
| 7 + post | **0.93** (0.97) | 1.00 (1.00) | **1.00** (1.00) | 1.00 (1.00) | 0.95 (1.00) | 0.34 (1.00) |
| F (no org) | 0.93 (0.97) | 1.00 (1.00) | 1.00 (1.00) | 1.00 (1.00) | 0.95 (1.00) | 1.00 (1.00) |

**What each step contributes (with `lg`):**

- **`age`** takes AGE from 0.00 to 1.00 F1, and overall recall from 0.85 to 0.90.
- **`mrn`** turns the "lucky" US-regex ID matches into real detections. The IDs
  are now found at 0.85 confidence instead of 0.01–0.05, so a threshold no
  longer wipes them out.
- **`registry`** removes 360 US-recognizer detections (ICD codes as driver
  licences, UHIDs reported 4 times). Precision dips slightly at this point only
  because the US hits had been overlapping real IDs; ID F1 reaches 1.00.
- **`hospital`** takes ORGANIZATION from 0.00 to 1.00 F1 and PHI-character coverage
  from 0.77 to 0.94.
- **`org`** (the `lg` NER model's ORGANIZATION) **hurts**: about 250 false
  organizations (`ICD`, `Kuppuswamy`, `Physical Examination: Cranial nerves`).
  Its only gain is covering locality names that `lg` misses as LOCATION
  (`Connaught Place`), which raises PHI-character coverage from 0.949 to 0.971.
  On the dev notes this trade is not worth it, so the final `lg` setup leaves it
  out. The decision was made on dev only.
- **`allow`** removes clinical words reported as PHI (exam signs, departments,
  herbs); PERSON F1 goes from 0.63 to 0.76.
- **`post`** gives the largest jump in exact-span quality: strict F1 goes from
  0.49 to 0.77, PERSON F1 to 0.93 and DATE_TIME F1 to 1.00. It removes
  durations and Hinglish "names", cuts spans at line breaks, strips `Dr.`/`Baby`,
  and joins `Jaipur` + `Rajasthan` and date + time.
- **`quiet`** changes no score; its effect is on logs (below).

**Remaining errors in the final `lg` setup (dev):** 5 patient names missed by the
model (`Soumya Das`, `Gursharan Singh` ×4); `Moga` labelled PERSON instead of
LOCATION (5); locality names missed (`Connaught Place`); `AM` left out of 3 times.

**Log leaks (G11):** no PHI appeared in any log message in the `lg` runs; this
problem belongs to the transformer pipeline (Stanford base, below).

### Ablation results: base model `en_core_web_trf` (dev notes 1–50)

| # | Step added | Any P / R / F1 | Overlap P / R / F1 | Strict F1 | PHI chars covered | Detections |
|---|---|---|---|---|---|---|
| – | shipped `trf` config (Phase 3, run C) | 0.862 / 0.954 / 0.905 | 0.771 / 0.794 / 0.782 | 0.518 | 0.812 | 960 |
| 0 | none (wrapper only) | 0.862 / 0.954 / 0.905 | 0.771 / 0.794 / 0.782 | 0.518 | 0.812 | 960 |
| 1 | + `age` | 0.868 / 0.964 / 0.914 | 0.782 / 0.894 / 0.834 | 0.572 | 0.814 | 1010 |
| 2 | + `mrn` | 0.880 / 0.964 / 0.920 | 0.802 / 0.894 / 0.845 | 0.637 | 0.841 | 1110 |
| 3 | + `registry` | 0.905 / 0.964 / 0.934 | 0.789 / 0.894 / 0.838 | 0.632 | 0.841 | 750 |
| 4 | + `hospital` | 0.911 / 0.994 / 0.951 | 0.802 / 0.994 / 0.888 | 0.685 | 0.974 | 800 |
| 5 | + `org` | 0.901 / 0.994 / 0.945 | 0.797 / 0.994 / 0.884 | 0.656 | 0.976 | 856 |
| 6 | + `allow` | 0.912 / 0.994 / 0.952 | 0.807 / 0.994 / 0.891 | 0.662 | 0.976 | 845 |
| 7 | + `post` | 0.994 / 0.994 / 0.994 | 0.964 / 0.994 / 0.979 | 0.946 | 0.987 | 521 |
| 8 | + `quiet` | 0.994 / 0.994 / 0.994 | 0.964 / 0.994 / 0.979 | 0.946 | 0.987 | 521 |
| **F** | **all except `org`** | **1.000 / 0.994 / 0.997** | **0.973 / 0.994 / 0.983** | **0.951** | 0.985 | 516 |

Per type, final `trf` setup (overlap F1): PERSON 0.97, AGE 1.00, DATE_TIME 0.97,
ID 1.00, LOCATION 1.00, ORGANIZATION 1.00.

With the transformer model, `org` is nearly harmless (it finds hospitals well),
but it still adds a few false organizations, so the final `trf` setup also
leaves it out. The transformer model fixes the remaining `lg` errors: it finds
`Gursharan Singh` and tags `Moga` and `Connaught Place` as locations. The
`allow` step matters much less here (PERSON was already 0.95), because the
transformer model rarely mistakes clinical words for names.

### Ablation results: Stanford de-identifier base (dev notes 1–50)

| # | Step added | Any P / R / F1 | Overlap P / R / F1 | Strict F1 | PHI chars covered | Log messages with PHI |
|---|---|---|---|---|---|---|
| – | shipped `transformers.yaml` (run D) | 0.878 / 0.900 / 0.889 | 0.796 / 0.800 / 0.798 | 0.395 | 0.841 | — |
| 0 | none | 0.878 / 0.900 / 0.889 | 0.796 / 0.800 / 0.798 | 0.395 | 0.841 | **4** |
| 1 | + `age` | 0.884 / 1.000 / 0.939 | 0.807 / 0.900 / 0.851 | 0.463 | 0.874 | 4 |
| 2 | + `mrn` | 0.895 / 1.000 / 0.945 | 0.826 / 0.900 / 0.861 | 0.487 | 0.874 | 4 |
| 3 | + `registry` | 0.931 / 1.000 / 0.965 | 0.824 / 0.900 / 0.861 | 0.479 | 0.874 | 4 |
| 4 | + `hospital` | 0.936 / 1.000 / 0.967 | 0.837 / 1.000 / 0.911 | 0.546 | 0.876 | 4 |
| 5 | + `org` (`HOSPITAL → ORGANIZATION`) | 0.932 / 1.000 / 0.965 | 0.821 / 0.900 / 0.859 | 0.498 | 0.876 | 4 |
| 6 | + `allow` | 0.932 / 1.000 / 0.965 | 0.821 / 0.900 / 0.859 | 0.498 | 0.876 | 4 |
| 7 | + `post` | 0.937 / 1.000 / 0.968 | 0.829 / 0.900 / 0.863 | 0.671 | 0.876 | 4 |
| 8 | + `quiet` | 0.937 / 1.000 / 0.968 | 0.829 / 0.900 / 0.863 | 0.671 | 0.876 | **0** |
| **F** | **all except `org`** | **0.937 / 1.000 / 0.968** | **0.921 / 1.000 / 0.959** | **0.750** | 0.876 | **0** |

- **`quiet` (G11) works:** the 4 log messages that contained patient PHI
  (name, age, UHID) disappear, with no change to any score.
- **`org` breaks LOCATION** (F1 0.68 → 0.00), because the Stanford model's only
  place label is HOSPITAL (see the G12 correction above).
- **`post` lowered ID F1** for this base (0.92 → 0.85). Not investigated further,
  because Stanford was not selected.
- **Ceiling.** Its strict F1 (0.750) and PHI coverage (0.876) stay below both spaCy
  bases, because its spans include titles and split addresses differently.

### Final selection (made on dev only, before any test-set scoring)

| System | Base model | Steps | Dev any F1 | Dev typed F1 | Dev strict F1 | Dev PHI chars |
|---|---|---|---|---|---|---|
| Baseline | `en_core_web_lg` | none (shipped default) | 0.782 | 0.727 | 0.391 | 0.740 |
| **Ours-accurate** | `en_core_web_trf` | age, mrn, registry, hospital, allow, post, quiet | **0.997** | **0.983** | **0.951** | **0.985** |
| **Ours-fast** | `en_core_web_lg` | age, mrn, registry, hospital, allow, post, quiet | 0.990 | 0.972 | 0.915 | 0.949 |
| Ours + Stanford | Stanford de-id | same | 0.968 | 0.959 | 0.750 | 0.876 |

Both *Ours-accurate* and *Ours-fast* go to the test set. Ours-accurate is best on
every dev measure. Ours-fast keeps the speed of the default model. The test set
also scores the shipped baseline and the shipped `trf` config, so the gain from
our plug-ins can be separated from the gain from the model.

## 5d. Phase 6: final evaluation on the held-out test notes (51–100)

The test notes were scored **once**, after the final systems had been chosen on
dev and their code frozen (all final runs postdate the last code change). The
predictions come from the same runs as the dev results; only the scored notes
differ. Test set: 50 notes, 500 PHI spans, 7,216 PHI characters.

### Main result

| System | Any P / R / F1 | Overlap P / R / F1 | Strict F1 | PHI chars covered | Missed PHI (any) | False alarms (any) |
|---|---|---|---|---|---|---|
| Baseline: Presidio default (`lg`) | 0.726 / 0.836 / 0.777 | 0.694 / 0.788 / 0.738 | 0.392 | 0.766 | 82 | 288 |
| Presidio shipped `trf` config | 0.863 / 0.962 / 0.910 | 0.770 / 0.800 / 0.785 | 0.525 | 0.833 | 19 | 132 |
| **Ours-fast** (`lg` + plug-ins) | 0.990 / 0.996 / **0.993** | 0.971 / 0.988 / **0.979** | **0.951** | **0.978** | **2** | **5** |
| **Ours-accurate** (`trf` + plug-ins) | 1.000 / 1.000 / **1.000** | 0.962 / 1.000 / **0.980** | **0.963** | **0.995** | **0** | **0** |

Other shipped configurations on the test notes, for reference: `en_core_web_sm`
F1 0.690; Stanford 0.890; GLiNER 0.677 (any rule). Ours + Stanford: 0.969.

**Same model, with and without our plug-ins:**

| Model | Presidio as shipped (any F1 / strict F1 / PHI chars) | + our plug-ins | Gain |
|---|---|---|---|
| `en_core_web_lg` | 0.777 / 0.392 / 0.766 | 0.993 / 0.951 / 0.978 | +0.216 F1, missed PHI 82 → 2 |
| `en_core_web_trf` | 0.910 / 0.525 / 0.833 | 1.000 / 0.963 / 0.995 | +0.090 F1, missed PHI 19 → 0 |

**Test results match dev.** Every final system scores within ±0.01 F1 of its dev
score (e.g. Ours-fast 0.990 dev → 0.993 test; Ours-accurate 0.997 → 1.000). So
the rules did not overfit to notes 1–50. They may still be fitted to the
*template* that both halves share (see Limitations).

### Per type on test (overlap rule, P / R)

| Type | Baseline | Ours-fast | Ours-accurate |
|---|---|---|---|
| PERSON | 0.48 / 0.99 | 0.91 / 0.99 | 0.96 / 1.00 |
| AGE | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| DATE_TIME | 0.69 / 1.00 | 1.00 / 1.00 | 0.89 / 1.00 |
| ID | 0.84 / 1.00* | 1.00 / 1.00 | 1.00 / 1.00 |
| LOCATION | 0.91 / 0.92 | 1.00 / 0.92 | 1.00 / 1.00 |
| ORGANIZATION | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 1.00 |

\* the baseline's ID recall again comes only from US regexes at 0.01–0.05 confidence (Section 5.3).

### Remaining errors on test

- **Ours-accurate:** no PHI missed. The only imperfect detections are wrong types
  on real PHI:
  - `22/` from `Age/Sex: 22/M` tagged DATE_TIME as well as AGE (12 times, plus
    `8 months/M` once);
  - `Anna Nagar` tagged PERSON (6);
  - `Kaithal` tagged PERSON (1).

  The `22/` case could be fixed by also stripping a trailing `/` in post-processing.
  It was **not** fixed, because changing the system after seeing test results
  would contaminate the test.
- **Ours-fast:**
  - 2 patient names missed by the `lg` model (`Soumya Das`, `Gursharan Singh`);
  - `Moga` tagged PERSON (4; still hidden);
  - `Anna Nagar` and `Viral Exanthem` tagged PERSON.

### Speed (idle machine, CPU only)

Measured with `eval/timing.py`: each system is loaded once, warmed up, then run
over all 100 notes twice (GLiNER once); median ms per note. Machine: Intel 64
(family 6 model 165) laptop CPU, Python 3.14, no GPU. Results: `results/timing.json`.

| System | ms / note (median) | Passes | Relative to baseline | Any F1 (test) |
|---|---|---|---|---|
| Baseline (`lg`, as shipped) | **38** | 39.2, 37.6 | 1× | 0.777 |
| **Ours-fast** (`lg` + plug-ins) | **45** | 51.4, 38.5 | ≈1× | **0.993** |
| Shipped `trf` config | 608 | 635.1, 580.1 | 16× | 0.910 |
| **Ours-accurate** (`trf` + plug-ins) | 596 | 648.6, 542.3 | 16× | **1.000** |
| Shipped Stanford (`transformers.yaml`) | 305 | 326.9, 283.4 | 8× | 0.890 |
| Ours + Stanford | 314 | 327.0, 301.8 | 8× | 0.969 |
| Shipped GLiNER (`slim.yaml`) | 2,127 | 2127.0 | 55× | 0.677 |

- **Our plug-ins cost almost nothing.** Pass-to-pass variation (about ±10%) is
  larger than the difference: Ours-fast's second pass (38.5 ms) equals the
  baseline (37.6 ms), and on `trf` and Stanford the times with and without
  plug-ins overlap. Regexes and post-processing are tiny next to running the NER model.
- **Ours-fast gives a better accuracy/speed trade-off** than any shipped model
  upgrade: higher F1 than the transformer configs at 1/13 to 1/50 of their
  run time.
- Load times: the first system measured (baseline, 24.5 s) also pays the one-time
  `import presidio_analyzer` (≈20–30 s, which pulls in torch). Later loads were
  3–15 s.
- Earlier ms/note values in Sections 5–5c were measured while downloads were
  running, and one overnight run included the laptop sleeping. Use this table
  for speed.

## 6. Gap analysis: mapped to Presidio's architecture

Component names follow `docs/PRESIDIO_ARCHITECTURE.md`. "Result" is the effect of
the fix as measured in the ablations (Section 5c) and on the test notes (Section 5d).

| # | Component | Gap | Evidence | Fix applied | Result |
|---|---|---|---|---|---|
| G1 | Recognizers | No AGE recognizer | AGE recall 0.00; bare ages (`45`) never found | `age` step: `AgeRecognizer` | ✅ AGE F1 0.00 → 1.00 (dev and test) |
| G2 | Recognizers | No Indian hospital-ID recognizer | IDs found only by US regexes at 0.01–0.05 | `mrn` step: `MedicalRecordNumberRecognizer` | ✅ IDs found at 0.85 confidence; ID F1 1.00 |
| G3 | Registry / config | ORGANIZATION ignored | 0 / 50 hospitals | `hospital` step: `HospitalNameRecognizer` (NER ORG tested as `org`, rejected) | ✅ ORGANIZATION F1 0.00 → 1.00 (optimistic: same hospitals in test) |
| G4 | Registry / config | US-only recognizers on for Indian text | 62 ICD codes flagged as US driver licence | `registry` step: India registry | ✅ all US-recognizer false alarms gone |
| G5 | NLP engine (NER model) | Non-names tagged PERSON | 150 false PERSON (Hinglish 67, medical terms 83) | `allow` + `post` steps; `trf` model | ✅ PERSON F1 0.63 → 0.95 (`lg`) / 0.98 (`trf`) on test |
| G6 | NLP engine (NER model) | Some Indian names and places mis-tagged | `Gursharan Singh` missed; `Anna Nagar`, `Moga` as PERSON | `trf` model (Ours-accurate) | 🟡 Fixed with `trf`; `lg` still misses 2 names on test |
| G7 | NLP engine (NER model) | Durations tagged DATE_TIME | 71 false DATE_TIME | `post` step: duration filter | ✅ DATE_TIME F1 → 1.00 (`lg`) |
| G8 | NLP engine / post-processing | Spans run across line breaks | 28 PERSON spans in dev | `post` step: cut at line breaks | ✅ strict F1 0.39 → 0.95 overall |
| G9 | Post-processing | Confidence scores not usable; duplicate types not merged | 3 score clusters; one UHID → 4 labels | own recognizers score 0.85; `post` merges overlaps | ✅ one label per span; thresholds no longer wipe out IDs |
| G10 | Input handling | Sensitive to line endings | Section 5.6 | Not fixed: documented only | ⬜ Open |
| G11 | NLP engine (Transformers) | **PHI written to logs**: alignment warnings in `spacy-huggingface-pipelines` print the start of the note | Section 5b, run D | `quiet` step: warning filter | ✅ PHI log messages 4 → 0 (Stanford base) |
| G12 | Model / configuration | Stanford model has no AGE and no LOCATION label; `transformers.yaml` maps an `AGE` label the model never emits, and must map `HOSPITAL` to either LOCATION or ORGANIZATION | Sections 5b, 5c | `age` + `hospital` steps; shipped mapping kept | ✅ Worked around (model limitation remains) |
| G13 | Configuration validation | Documented `supported_countries` registry option is rejected by the validator | Section 5c | per-recognizer `enabled` flags | ✅ Worked around; to report upstream |
| G14 | Recognizers (India) | `InPanRecognizer` low pattern has unbounded lookaheads → ordinary 10-letter words become PAN numbers | Section 5c | `FixedInPanRecognizer` (bounded lookaheads) | ✅ Fixed in our system; to report upstream |

## 7. Problems met and how they were solved

| Problem | Solution |
|---|---|
| GitHub API rate limit during the repo check | Blobless `git clone` to get every file's hash without downloading contents |
| GitHub downloads at ~40 KB/s (400 MB model would take ~3 h) | Resumed from the partial download, fetched the rest in 16 parallel byte ranges (~240 KB/s), verified every file's CRC inside the wheel |
| Hugging Face mirror only had model 3.7.1 (incompatible with spaCy 3.8) | Not used |
| Windows `\r\n` line endings shift character offsets | All scripts read notes through one function (`eval/common.py`, `newline=''`) |
| Gold-standard review could not be done by a human | Systematic AI review of every line (Section 4.1); recorded as a limitation |
| `supported_countries` rejected by Presidio's validator (G13) | Generated registry with per-recognizer `enabled` flags |
| Enabling Indian recognizers "improved" hospital coverage by accident (G14) | Traced to the PAN lookahead bug; replaced with `FixedInPanRecognizer` |
| Laptop slept overnight during one ablation run | Scores unaffected; all speeds re-measured on an idle machine (`eval/timing.py`) |

## 8. Conclusions, limitations and next steps

### Conclusions

1. **Presidio as shipped is not ready for Indian clinical notes.** Its default
   setup reflects US/UK, general-domain assumptions:
   - recognizers are US-format;
   - the NER model is trained on web and news text;
   - ORGANIZATION is switched off;
   - there is no age or medical-record-number recognizer.

   On these notes it leaves 23% of PHI characters visible and raises more false
   alarms than correct detections of some types.
2. **Its architecture is the right one to fix this.** Every gap we found could
   be closed through extension points Presidio already offers:
   - custom recognizers;
   - registry configuration;
   - NLP-engine configuration;
   - the allow-list;
   - a thin post-processing wrapper.

   No Presidio code was changed.
3. **Most of the gain comes from rules, not from a bigger model.** With the
   default `lg` model, our plug-ins take test F1 from 0.777 to 0.993 at the same
   speed. Swapping in the transformer model alone gives 0.910 at about 15× the cost.
4. **The ablation shows which plug-in matters most:**

   | Biggest effect on… | Plug-in(s) |
   |---|---|
   | recall | `age`, `hospital` |
   | precision | `registry`, `allow` |
   | exact boundaries | `post` |
   | privacy of logs | `quiet` (no effect on scores) |

5. **Several issues are worth reporting upstream:** G14 (PAN bug, with a fix),
   G13 (validator vs. documented option), G11 (PHI in logs via a dependency),
   and the threshold problem behind G9 (scores cluster at three values).

### Limitations

- **One template.** All 100 English notes come from the same template with a small
  pool of names, hospitals and addresses. The held-out test checks that the rules
  are not fitted to *notes 1–50*, but not that they carry over to other formats.
  Hospital-name results in particular are optimistic, because the test notes use
  the same 10 hospitals and our hospital recognizer includes an acronym list.
- **Gold standard reviewed by the AI assistant, not a human.** There is no
  inter-annotator agreement. The labels are simple template fields, which limits
  the risk, but a human spot-check would strengthen the result.
- **Small test set.** 50 notes and 500 PHI spans. A difference of one or two errors
  moves F1 by about 0.002–0.004.
- **English only.** The 62 German notes are not yet evaluated.
- **CPU only.** Speeds are for this laptop's CPU. Transformer models would be
  much faster on a GPU.

### Next steps (proposed)

1. German notes: Presidio's multilingual config + German recognizers, with gold
   labels (GraSCCo's published annotations if available).
2. Test on differently formatted English clinical notes to measure generalisation
   beyond the template.
3. A human spot-check of ~10 gold-standard notes.
4. Report G11, G13 and G14 to the Presidio project.

## 9. How to reproduce

```bash
# from the project root, using the project venv
.venv/Scripts/python.exe eval/make_gold.py           # draft labels + review page
.venv/Scripts/python.exe eval/freeze_gold.py         # apply corrections -> gold.jsonl
.venv/Scripts/python.exe eval/run_clinical.py --name baseline
.venv/Scripts/python.exe eval/score.py --name baseline --split dev

# Phase 3 (needs: pip install "presidio-analyzer[transformers,gliner]" torch,
#          en_core_web_sm / en_core_web_trf 3.8.0)
C=.venv/Lib/site-packages/presidio_analyzer/conf
.venv/Scripts/python.exe eval/run_clinical.py --name cfg_spacy_sm      --nlp-conf ourpresidio/conf/spacy_sm.yaml
.venv/Scripts/python.exe eval/run_clinical.py --name cfg_spacy_trf     --nlp-conf ourpresidio/conf/spacy_trf.yaml
.venv/Scripts/python.exe eval/run_clinical.py --name cfg_stanford_deid --nlp-conf $C/transformers.yaml
.venv/Scripts/python.exe eval/run_clinical.py --name cfg_gliner        --analyzer-conf $C/slim.yaml
# score each with eval/score.py --split dev, then:
.venv/Scripts/python.exe eval/compare.py --split dev baseline cfg_spacy_sm cfg_spacy_trf cfg_stanford_deid cfg_gliner

# Phase 5: ablations on all three bases (+ final step sets), scored on dev
bash eval/run_all_ablations.sh
# one system by hand, e.g. Ours-fast:
.venv/Scripts/python.exe eval/run_clinical.py --name ours_lg_final --ours --base lg \
    --steps age mrn registry hospital allow post quiet

# Phase 6: score the frozen runs on the held-out notes, then speed on an idle machine
for r in baseline cfg_spacy_trf ours_lg_final ours_trf_final; do
  .venv/Scripts/python.exe eval/score.py --name $r --split test; done
.venv/Scripts/python.exe eval/compare.py --split test baseline cfg_spacy_trf ours_lg_final ours_trf_final
.venv/Scripts/python.exe eval/timing.py
```

Using our system in other code:

```python
from ourpresidio.engine import ClinicalAnalyzer
analyzer = ClinicalAnalyzer(base="lg", steps=["age", "mrn", "registry", "hospital",
                                              "allow", "post", "quiet"])
results = analyzer.analyze(text)   # list of Presidio RecognizerResult
```

## 10. Files

| Path | What |
|---|---|
| `data/Clinical_text/` | the 100 English notes (`1.txt`–`100.txt`); the 62 German notes are not included in this repository |
| `eval/ANNOTATION_GUIDELINE.md` | labelling rules and review record |
| `eval/common.py` | shared note loader, splits, labels |
| `eval/make_gold.py` | drafts gold labels, builds `review.html` |
| `eval/review_template.html`, `eval/gold/review.html` | review page template; the generated page is not committed (run `make_gold.py` to regenerate) |
| `eval/gold/gold_draft.jsonl` | draft labels before review |
| `eval/freeze_gold.py` | applies corrections, writes `gold.jsonl` |
| `eval/run_clinical.py` | runs Presidio, saves detections |
| `eval/score.py` | metrics, threshold sweep, error lists |
| `eval/gold/gold.jsonl` | **frozen gold standard** (1,000 spans) |
| `eval/gold/corrections.json`, `changes.jsonl` | review corrections and their record |
| `eval/compare.py` | side-by-side Markdown tables for any set of runs |
| `ourpresidio/conf/spacy_sm.yaml`, `spacy_trf.yaml` | Presidio's `default.yaml` with only the model name changed |
| `results/baseline/` | `predictions.jsonl`, `run_info.json`, `metrics_dev.json/.csv`, `errors_dev.jsonl` |
| `results/cfg_spacy_sm/`, `cfg_spacy_trf/`, `cfg_stanford_deid/`, `cfg_gliner/` | the same files for each Phase 3 run |
| `results/control_provider_lg/` | control run (default config loaded via `AnalyzerEngineProvider`) |
| `ourpresidio/engine.py` | `ClinicalAnalyzer`: builds Presidio from configs, adds recognizers, allow-list, post-processing, log filter |
| `ourpresidio/recognizers.py` | `AgeRecognizer`, `MedicalRecordNumberRecognizer`, `HospitalNameRecognizer`, `FixedInPanRecognizer` |
| `ourpresidio/clinical_vocab.py` | allow-list vocabulary |
| `ourpresidio/conf/registry_india.yaml` | generated registry: other countries off, India on |
| `ourpresidio/conf/spacy_*_org.yaml`, `stanford_fixed.yaml` | NLP configs used by the `org` step |
| `eval/ablation.sh`, `eval/run_all_ablations.sh` | cumulative ablation drivers |
| `eval/timing.py` | speed measurement → `results/timing.json` |
| `results/timing.json` | idle-machine speeds for all final and shipped systems |
| `results/ours_<base>_<n>_<step>/`, `ours_<base>_final/` | ablation and final runs (`metrics_dev.*`, `metrics_test.*`, `errors_*.jsonl`) |

## 11. Change log

| Date | Step |
|---|---|
| 2026-10-05 | Repository verified against GitHub (914/918 identical; differences outside presidio-analyzer). |
| 2026-10-05 | Plan approved: English notes first, semi-automatic gold labels, dev/test split. |
| 2026-10-05 | Annotation guideline written; 1,000 draft labels generated; full review; 8 corrections; gold frozen. |
| 2026-10-05 | `en_core_web_lg` 3.8.0 installed (parallel download, CRC-verified). |
| 2026-10-05 | Baseline run and scored on dev. Gap analysis first pass (G1–G10). Line-ending side experiment. |
| 2026-10-05 | Phase 3 started: installed `[transformers,gliner]` extras + torch; control check passed (provider = AnalyzerEngine()); run B (`en_core_web_sm`) scored. |
| 2026-10-05 | Phase 3 done: runs C (trf), D (Stanford), E (GLiNER) scored; new gaps G11 (PHI in logs) and G12 (config label mapping); `eval/compare.py` added. |
| 2026-10-05 | Phase 5: `ourpresidio/` built (3 recognizers, India registry, allow-list, post-processing, log filter). Found G13 (validator rejects documented option) and G14 (PAN recognizer bug). Fixed two bugs of our own via the ablation. Runner now counts PHI in log messages. |
| 2026-10-05 | Phase 5 `lg` ablation complete: final `lg` setup (no `org`) F1 0.990 / typed 0.972 / strict 0.915 on dev. Added comma/space merge of same-type spans. |
| 2026-10-06 | Phase 5 done: `trf` and Stanford ablations; G12 corrected (Stanford has no location label); `quiet` removes all 4 PHI log leaks. Final systems chosen on dev: Ours-accurate (`trf`) and Ours-fast (`lg`). A MIMIC-IV names check was considered and dropped (out of scope). |
| 2026-10-06 | Phase 6 done: test notes 51–100 scored once. Ours-fast F1 0.993, Ours-accurate 1.000 vs baseline 0.777 (any type). Speed re-measured on idle machine (`eval/timing.py`). Key results, conclusions and limitations written. |
| 2026-10-06 | Report consistency pass: gap table now shows the fix applied and measured result for G1–G14; stale timing note, import time, problems table, version table and file list updated. |
