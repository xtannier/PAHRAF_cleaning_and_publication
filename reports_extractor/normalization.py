from typing import Any, Dict, List, Tuple
import regex as re
from unidecode import unidecode


MEDICAL_SPECIALTIES_FR_EN: dict[str, str] = {
    "CANCERO ADULTE": "Oncology",
    "PNEUMOLOGIE": "Pulmonology",
    "ANATOMOPATHOLOGIE": "Pathology",
    "CHIRURGIE VISCERALE": "Digestive Surg.",
    "MALADIES INFECTIEUSES": "Infectious Dis.",
    "CHIR ORTHO ET TRAUMATO": "Ortho & Trauma Surg.",
    "NEUROLOGIE": "Neurology",
    "MEDECINE INTERNE": "Internal Med.",
    "GYNECOLOGIE": "Gynecology",
    "UROLOGIE": "Urology",
    "OBSTETRIQUE": "Obstetrics",
    "HEPATO-GASTRO-ENTERO": "Gastro-Hepatology",
    "MEDECINE GERIATRIQUE": "Geriatrics",
    "HEMATOLOGIE CLINIQUE": "Hematology",
    "NEPHROLOGIE": "Nephrology",
    "MEDECINE INTER-SPECIALITES": "Gen. Internal Med.",
    "CARDIOLOGIE": "Cardiology",
    "MEDECINE PEDIATRIQUE": "Pediatrics",
    "REANIMATION": "Critical Care",
    "CHIR.CARDIO-VASC.": "Cardiovasc. Surg.",
}

DOCTYPE_FR_EN: dict[str, str] = {
    "ANAPATH": "Pathology",
    "ANAPATH2": "Pathology",
    "CRC": "Consultation",
    "CRO": "Surgical Report",
    "CRH": "Hospital Stay",
    "MATERNITE": "Maternity",
    "NAISSANCE": "Childbirth",
    "URGENCES": "Emergency",
    "ACCOUCHEMENT": "Childbirth",
}

DURATION_UNITS = {
    "h": "heures",
    "heure": "heures",
    "heures": "heures",
    "j": "jours",
    "jour": "jours",
    "jours": "jours",
    "sem": "semaines",
    "semaine": "semaines",
    "semaines": "semaines",
    "m": "mois",
    "mois": "mois",
    "a": "ans",
    "an": "ans",
    "ans": "ans",
}

USE_CASE_NAMES = {
    "Pool Général": "General",
    "general": "General",
    "CU 1": "CU 1 - Pseudonymisation",
    # "CU 1": "General",  # CU1 pseudonymisation use case uses general reports, so we map it to "General"
    "CU 2": "CU 2 - ICD-10 coding",
    "CU 5a": "CU 5a - Oncology (biomarkers)",
    "CU 5b": "CU 5b - Oncology (response to treatment)",
    "CU 6": "CU 6 - Infectiology",
}

# examples of duration: "2 ans", "3 mois", "5 j"
DURATION_REGEX = re.compile(
    r"(un|\d+)\s*(" + "|".join(DURATION_UNITS.keys()) + r")( ans)?\b"
)  # The last "ans" is here because some scenarii have been mistakenly written with "2 ans ans" instead of "2 ans"
# example of text: "Tumeur maligne de la partie centrale du sein [C501]"
DIAGNOSIS_REGEX = re.compile(r"^(.*)\s+[\(\[]([A-Za-z0-9\.\+]+)[\)\]]?[ \.]*$")
# example of text for procedure:
# "Ligature des artères hémorroïdaires avec guidage doppler, avec mucopexie, par voie anale [EDSD011]"
PROCEDURE_REGEX = re.compile(r"^(.*)\s+[\(\[]([A-Z0-9\+]+)[\)\]]?[ \.]*$")

# Compile regex patterns
CRO_PATTERN = re.compile(r"^[#\*][#\*] *COMPTE[- ]RENDU OP[EÉ]RATOIRE")
CRC_PATTERN = re.compile(r"^[#\*][#\*] *COMPTE[- ]RENDU DE CONSULTATION")
CRH_PATTERN = re.compile(r"^[#\*][#\*] *COMPTE[- ]RENDU D...............")
CRH_PATTERN_ANAPATH = re.compile(r"^[#\*][#\*] *COMPTE[- ]RENDU ANATO.....")
CRH_PATTERN_ANAPATH2 = re.compile(r"^[#\*][#\*] *COMPTE-RENDU ANATO.* COMP.*")
URGENCES_PATTERN = re.compile(r"^[#\*][#\*].*COMPTE[- ]RENDU DE PASSAGE AUX URGENCES")
URGENCES_PATTERN_2 = re.compile(r"^[#\*][#\*].*COMPTE[- ]RENDU DES URGENCES")
ACCOUCHEMENT_PATTERN = re.compile(r"^[#\*][#\*].*COMPTE[- ]RENDU D'ACCOUCHEMENT")
MATERNITE_PATTERN = re.compile(
    r"^[#\*][#\*].*COMPTE DE RENDU DE MATERNIT"
)  # the typo is intentional
SERVICE_PATTERN = re.compile(r"^[#\*][#\*] *SERVICE D")


# Compiled regex pattern for extracting metadata from file paths
# e.g., CRH_specialty_12345_ABC.docx
FILEPATH_PATTERN = re.compile(
    r"[^_]*(\w\w\w)_([\w_-]+)_+(\d\d\d\d\d)[_-]+(\w\w\w).*.docx",
    re.IGNORECASE,
)


class InvalidPathException(Exception):
    """
    Raised when the original path do not fit the expected pattern
    """

    def __init__(self, filepath: str):
        self.message = f"{filepath} does not match the expected pattern"
        super().__init__(self.message)


def path_parser(path: str) -> Tuple[str, str, Dict[str, str]]:
    """
    Extract metadata from path name

    Parameters
    ----------
    path : str
        The path containing the name of the original file

    Raises
    ------
    ValueError
        If path doesn't match the expected pattern

    Returns
    -------
    Tuple[str, str, Dict[str, str]]
        A triple containing
        1. the patient id as infered from the file path
        2. the specialty of the document
        3. any other metadata extracted from the path

    Raises
    ------
    InvalidPathException
        If the path doesn't match the expected pattern
    """
    # Remove white spaces from path
    clean_path = path.replace(" ", "")
    matcher = FILEPATH_PATTERN.match(clean_path)
    if not matcher:
        raise InvalidPathException(clean_path)
    specialty = matcher.group(2).upper()
    local_id = matcher.group(3)
    return (
        local_id,
        specialty,
        {},
    )


class NormalizationException(ValueError):
    """
    Raised when the original path do not fit the expected pattern
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


def sex_normalization(text: str) -> str:
    """
    Normalize sex field by converting values to "M" and "F"

    Parameters
    ----------
    text : str
        Raw sec text from the report

    Returns
    -------
    str
        Normalized sex in the format M|F

    Raises
    ------
    ValueError
        If the sex format is unexpected
    """
    if text.lower() in ("homme", "m"):
        return "M"
    elif text.lower() in ("femme", "f"):
        return "F"
    else:
        raise NormalizationException(f"Unexpected sex format: |{text}|")


def duration_normalization(text: str) -> Dict[str, Any] | None:
    """
    Normalize age field by extracting numeric value and unit.

    Parameters
    ----------
    text : str
        Raw age text from the report.

    Returns
    -------
    str
        Normalized age in the format "<number> <unit>".

    Raises
    -------
    ValueError
        If the age format is unexpected.
    """
    # Strip unwanted characters (especially "xxxx" which is the default value and
    # should not be normalized to None)
    text = text.strip(" -•/xX.\n")
    if text == "":
        return None
    if "\n" in text:
        raise NormalizationException(
            f"Unexpected duration format with newline: |{text}|"
        )
    # "Ambulatoire" = 0 days
    if "ambulatoire" in text.lower() or "hdj" in text.lower():
        return {"value": 0, "unit": "jours"}
    # Match <number> + <unit>
    match = DURATION_REGEX.match(text.lower())
    if match:
        number = match.group(1)
        unit = match.group(2)
        if unit in DURATION_UNITS:
            unit = DURATION_UNITS[unit]
        else:
            raise NormalizationException(
                f"Unexpected duration unit: |{unit}| in |{text}|"
            )
        if number == "un":
            number = 1
        return {"value": int(number), "unit": unit}
    # Match <number> alone (assumed to be in years)
    elif re.match(r"^\d+$", text.strip()):
        return {"value": int(text.strip()), "unit": "ans"}
    else:
        raise NormalizationException(f"Unexpected duration format: |{text}|")


def free_text_diagnosis_normalization(text: str) -> List[Dict[str, str]] | None:
    """
    Normalize free text diagnosis by stripping whitespaces and bullets.

    Parameters
    ----------
    text : str
        Raw free text diagnosis from the report.

    Returns
    -------
    str
        Normalized free text diagnosis.

    Raises
    ------
    NormalizationException
        If the free text diagnosis format is unexpected.
    """
    result = []
    for line in text.split("\n"):
        stripped_text = text.strip(" -•/._")
        if stripped_text == "" or stripped_text.lower() in (
            "aucun",
            "néant",
            "x",
            "0",
            "ras",
        ):
            continue
        # Sanity checks
        elif (
            "(en texte libre, sans codage)" in stripped_text.lower()
            or "que vous avez choisis" in stripped_text.lower()
        ):
            raise NormalizationException(
                f"Unexpected free text diagnosis format: |{text}|"
            )
        else:
            result.append({"description": stripped_text})
    if len(result) == 0:
        return None
    return result


def diagnosis_normalization(text: str) -> List[Dict[str, str]] | None:
    """
    Normalize diagnosis code by stripping whitespace and converting to uppercase.
    Example of expected format: "Description du diagnostic [CODE]"

    Parameters
    ----------
    text : str
        Raw diagnosis code from the report.

    Returns
    -------
    List[Dict[str, str]] | None
        Normalized diagnosis codes and descriptions
    """
    # example of text: "Tumeur maligne de la partie centrale du sein [C501]"
    # example of output: {"code": "C501", "description": "Tumeur maligne de la partie centrale du sein"}
    result = []
    for line in text.split("\n"):
        stripped_text = line.strip(" -•/._")
        if stripped_text == "" or stripped_text.lower() in (
            "aucun",
            "néant",
            "x",
            "0",
            "ras",
        ):
            continue
        match = DIAGNOSIS_REGEX.match(stripped_text)
        if match:
            description = match.group(1).strip()
            code = match.group(2).strip().upper()
            result.append({"code": code, "description": description})
        else:
            # if no code is found, treat as free text diagnosis
            norm = free_text_diagnosis_normalization(line)
            if norm is not None:
                result.extend(norm)

    if len(result) == 0:
        return None
    return result


def procedure_normalization(text: str) -> List[Dict[str, str]] | None:
    """
    Normalize procedure codes by stripping whitespace and converting to uppercase.

    Parameters
    ----------
    text : str
        Raw procedure code from the report.

    Returns
    -------
    List[Dict[str, str]] | None
        Normalized procedure code and description
    """
    # example of text: "Ligature des artères hémorroïdaires avec guidage doppler, avec mucopexie, par voie anale [EDSD011]"
    # example of output: {"code": "EDSD011", "description": "Ligature des artères hémorroïdaires avec guidage doppler, avec mucopexie, par voie anale"}
    result = []
    for line in text.split("\n"):
        stripped_text = line.strip(" -•/._")
        if stripped_text == "" or stripped_text.lower() in ("aucun", "néant", "x"):
            return None
        match = PROCEDURE_REGEX.match(stripped_text)
        if match:
            description = match.group(1).strip()
            code = match.group(2).strip().upper()
            result.append({"code": code, "description": description})
        else:
            raise NormalizationException(f"Unexpected procedure format: |{text}|")
    return result


def admission_mode_normalization(text: str) -> str:
    """
    Normalize admission mode by stripping whitespace.

    Parameters
    ----------
    text : str
        Raw admission mode from the report.

    Returns
    -------
    str
        Normalized admission mode
    """
    text = text.strip(" -•/._").lower()
    if text == "domicile (modifier pour urgences ?)":
        return "domicile (à modifier pour entrée par les urgences)"
    if text == "domicile > changer pour entrée par les urgences":
        return "domicile (à modifier pour entrée par les urgences)"
    if text == "domicile > à modifier pour urgences":
        return "domicile (à modifier pour entrée par les urgences)"
    if text == "entrée via les urgences":
        return "entrée par les urgences"
    if text == "urgence":
        return "urgences"
    return text


def discharge_mode_normalization(text: str) -> str:
    """
    Normalize discharge mode by stripping whitespace.

    Parameters
    ----------
    text : str
        Raw discharge mode from the report.

    Returns
    -------
    str
        Normalized discharge mode
    """
    text = text.strip(" -•/._").lower()
    if text == "patient décédé":
        return "décès"
    if text == "patiente décédée":
        return "décès"
    if text == "transfert en soins de suite et réducation":
        return "transfert en soins de suite et rééducation"
    if text == "transgert en soins de suite et réducation":
        return "transfert en soins de suite et rééducation"
    if text == "transfert en soins de suite et réeducation":
        return "transfert en soins de suite et rééducation"
    return text


def report_type_normalization(text: str) -> str | None:
    """
    Normalize report types from section headers.
    - If the report starts by "COMPTE-RENDU D'HOSPITALISATION", return "CRH"
    - If the report starts by "COMPTE-RENDU OPERATOIRE", return "CRO"
    - If the report starts by "COMPTE-RENDU DE CONSULTATION", return "CRC"
    - Skip "Service d..." headers by returning None
    - If the report type is not recognized, raise an exception.


    Parameters
    ----------
    text : str
        Raw report type from the report.

    Returns
    -------
    str
        Normalized report type

    Raises
    ------
    NormalizationException
        If the report type format is unexpected.
    """
    normalized_text = unidecode(text.strip()).upper()
    if CRO_PATTERN.match(normalized_text):
        return "CRO"
    elif CRC_PATTERN.match(normalized_text):
        return "CRC"
    elif CRH_PATTERN_ANAPATH2.match(normalized_text):
        return "ANAPATH2"
    elif URGENCES_PATTERN.match(normalized_text):
        return "URGENCES"
    elif URGENCES_PATTERN_2.match(normalized_text):
        return "URGENCES"
    elif CRH_PATTERN.match(normalized_text):
        return "CRH"
    elif CRH_PATTERN_ANAPATH.match(normalized_text):
        return "ANAPATH"
    # Special headers for maternity and accouchement
    elif ACCOUCHEMENT_PATTERN.match(normalized_text):
        return "ACCOUCHEMENT"
    elif MATERNITE_PATTERN.match(normalized_text):
        return "MATERNITE"
    # Skip headers starting with "SERVICE D..."
    elif SERVICE_PATTERN.match(normalized_text):
        return None
    else:
        raise NormalizationException(f"Unexpected report type format: |{text}|")


FIELD_CLEANING_FUNCTIONS = {
    "age": duration_normalization,
    "length_of_stay": duration_normalization,
    "primary_diagnosis": diagnosis_normalization,
    "secondary_diagnoses_from_the_list": diagnosis_normalization,
    "sex": sex_normalization,
    "primary_procedure": procedure_normalization,
    "other_diagnoses": diagnosis_normalization,
    "admission_mode": admission_mode_normalization,
    "discharge_mode": discharge_mode_normalization,
}
