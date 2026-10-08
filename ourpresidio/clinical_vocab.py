"""Clinical words that are never PHI, passed to Presidio's analyze(allow_list=...) (G5).

The *categories* were chosen from the kinds of false alarms seen on the dev
notes; each category is filled with general clinical vocabulary, not with the
exact error strings, so that the list carries over to other notes.
Presidio's "exact" allow-list matching is case-sensitive and compares the whole
detected span, so every term is added in its common case variants.
"""

EXAM_SIGNS = [
    "Pallor", "Icterus", "Jaundice", "Cyanosis", "Clubbing", "Koilonychia", "Lymphadenopathy",
    "Edema", "Oedema", "Pedal edema", "Dehydration", "Crepitations", "Crepts", "Rhonchi",
    "Wheeze", "Wheezing", "Tenderness", "Guarding", "Rigidity", "Ascites", "Hepatomegaly",
    "Splenomegaly", "Cachexia", "Cachexic", "Afebrile", "Febrile", "Tachycardia", "Bradycardia",
    "Tachypnea", "Murmur", "Rales", "Petechiae", "Rash", "Pruritus", "Anemia", "Anaemia",
    "Pallor present", "Organomegaly", "Hyperactive", "Hypoactive",
]

SPECIALTIES = [
    "Neurology", "Cardiology", "Oncology", "Orthopaedics", "Orthopedics", "Pediatrics",
    "Paediatrics", "General Medicine", "General_medicine", "Internal Medicine", "Medicine",
    "General Surgery", "Surgery", "Gynaecology", "Gynecology", "Obstetrics", "Dermatology",
    "Psychiatry", "Nephrology", "Urology", "Gastroenterology", "Pulmonology",
    "Pulmonary Medicine", "Endocrinology", "Rheumatology", "Hematology", "Haematology",
    "Ophthalmology", "ENT", "Radiology", "Anaesthesiology", "Anesthesiology", "Emergency",
    "Emergency Medicine", "Casualty", "ICU", "NICU", "PICU", "OPD", "IPD", "Physiotherapy",
]

ROLES = [
    "Pediatrician", "Paediatrician", "Cardiologist", "Pulmonologist", "Neurologist",
    "Oncologist", "Nephrologist", "Gastroenterologist", "Surgeon", "Cardiac Surgeon",
    "Neurosurgeon", "Orthopedic Surgeon", "Physician", "Consultant", "Resident", "Intern",
    "Nurse", "Staff Nurse", "Registrar", "Radiologist", "Pathologist", "Anaesthetist",
    "Psychiatrist", "Dermatologist", "Gynecologist", "Gynaecologist", "Obstetrician",
]

DOCUMENT_WORDS = [
    "Patient", "Patients", "Hospital", "Doctor", "Discharge", "Discharge Summary", "Summary",
    "Signature", "Admission", "Diagnosis", "Investigations", "Advice", "Follow-up", "Follow up",
]

INDIAN_REMEDIES = [
    "Tulsi", "Haldi", "Haldi milk", "Ashwagandha", "Neem", "Giloy", "Triphala", "Amla",
    "Ayurveda", "Ayurvedic", "Kadha", "Chyawanprash", "Brahmi", "Shilajit", "Jeera", "Ajwain",
]

BODY_REGIONS = [
    "Epigastric", "Epigastrium", "Hypogastric", "Hypochondrium", "Umbilical", "Periumbilical",
    "Iliac fossa", "Lumbar", "Thoracic", "Cervical", "Abdomen", "Chest", "Flank",
]


def _variants(term):
    return {term, term.lower(), term.upper(), term.title(), term[:1].upper() + term[1:]}


ALLOW_LIST = sorted({
    v
    for group in (EXAM_SIGNS, SPECIALTIES, ROLES, DOCUMENT_WORDS, INDIAN_REMEDIES, BODY_REGIONS)
    for term in group
    for v in _variants(term)
})
