import regex as re


# Constants for report extraction

# Section style headers used in the reports
SECTION_STYLE = "## "

# Fields expected in different sections of the reports
# These mappings are used to identify and extract relevant information from the reports.
EXPECTED_FIELDS_IN_SCENARIO = {
    "Nom": "name",
    "Age": "age",
    "Sexe": "sex",
    "Mode d'entrée": "admission_mode",
    "Mode de sortie": "discharge_mode",
    "Diagnostic principal motivant l'hospitalisation (code CIM 10)": "primary_diagnosis",
    "Diagnostic principal (code CIM 10)": "primary_diagnosis",
    "Acte principal": "primary_procedure",
    "Mode de prise en charge (médecine, chirurgie, etc.)": "type_of_care",
}


#  Fields expected in the structured abstract section of the reports
EXPECTED_FIELDS_IN_STRUCTURED_ABSTRACT = {
    "Diagnostic principal motivant l'hospitalisation (code CIM 10)": "primary_diagnosis",
    "Diagnostic principal motivant l'hospitalisation (CIM-10)": "primary_diagnosis",
    "Acte principal": "primary_procedure",
    "Mode d'entrée": "admission_mode",
    "Mode de sortie": "discharge_mode",
    "Durée de séjour": "length_of_stay",
    "Durée totale d'hospitalisation": "length_of_stay",
    "Durée de séjour (en réanimation)": "length_of_stay",
    "Diagnostics associés": "secondary_diagnoses_from_the_list",
    "Sélection des diagnostics retenus dans la liste initiale": "secondary_diagnoses_from_the_list",
    "Ajout de diagnostic": "other_diagnoses",
    "Autres diagnostics que vous avez choisis (en texte libre, sans codage)": "other_diagnoses",
    "Autres diagnostics que vous avez choisis": "other_diagnoses",
    "Autres diagnostics": "other_diagnoses",
    "Autre diagnostic": "other_diagnoses",
    "Acte CCAM principal": "primary_procedure",
    "Mode de prise en charge (médecine, chirurgie, etc.)": "type_of_care",
}

# Compiled regex patterns for extracting fields from the reports
EXPECTED_PATTERNS_IN_SCENARIO: dict[re.Pattern, str] = {
    re.compile(rf"{re.escape(key)}(?:\s*:\s*|\s+|\s*$)(.*)"): value
    for key, value in EXPECTED_FIELDS_IN_SCENARIO.items()
}

# Compiled regex patterns for extracting fields from the structured abstract section
EXPECTED_PATTERNS_IN_STRUCTURED_ABSTRACT: dict[re.Pattern, str] = {
    re.compile(rf"{re.escape(key)}(?:\s*:\s*|\s+|\s*$)(.*)"): value
    for key, value in EXPECTED_FIELDS_IN_STRUCTURED_ABSTRACT.items()
}

# Compiled regex patterns for section headers
# RECORD_PATTERN = re.compile(r"^\s*COMPTE[ -]RENDU")

ABSTRACT_PATTERN = re.compile(r"^([#\*][#\*])*\s*RÉSUMÉ\s+STRUCTURÉ")

# REVIEWED_FILEPATH_PATTERN = re.compile(
#     r".*CRH_([\w_-]+)_+(\d\d\d\d\d)[_-]+(\w\w\w)[_-]+r[eé]dig[eé][_-]+(\w\w\w)[_-]+relu.docx",
#     re.IGNORECASE,
# )

# Constant for JSON headers
# JSON_TEMPLATE = {"reports_extractor_version": "1.0.0", "reports": []}
