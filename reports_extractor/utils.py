from typing import Any, List, Dict, Optional
from googleapiclient.discovery import HttpError, build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
import io
import os
from os import makedirs
from os.path import exists, isdir, join
import pypandoc
from regex import Match
from unidecode import unidecode
import random
import openpyxl
import shutil
from .constants import (
    EXPECTED_PATTERNS_IN_SCENARIO,
    EXPECTED_PATTERNS_IN_STRUCTURED_ABSTRACT,
    ABSTRACT_PATTERN,
    SECTION_STYLE,
)
from .normalization import (
    NormalizationException,
    InvalidPathException,
    path_parser,
    report_type_normalization,
    FIELD_CLEANING_FUNCTIONS,
    USE_CASE_NAMES,
)
from .filters import *  # noqa: F403
from slugify import slugify
import logging
import edsnlp

logger = logging.getLogger("utils")
random.seed(10)


class DocumentParsingException(Exception):
    """
    Raised when the parsing of a docx document fails
    """

    def __init__(self, filepath: str, message: str):
        self.message = f"{filepath} was not parsed correctly: {message}"
        super().__init__(self.message)


class WordCounter:
    """A simple word counter for text documents."""

    def __init__(self):
        """
        Initialize the WordCounter ."""
        self.nlp = edsnlp.blank("eds")

    def count_words(self, text: str) -> int:
        """
        Count the number of words in the text.

        Parameters
        ----------
        text : str
            The input text.

        Returns
        -------
        int
            The number of words in the text.
        """
        words = self.nlp(text)
        return len(words)


class Patient:
    """A patient with the associated scenario and the written documents."""

    def __init__(
        self,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        scenario: Optional[Dict[str, str]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        structured_abstract: Optional[Dict[str, str]] = None,
        add_diagnostic_codes_to_structured_abstract: bool = True,
    ):
        """
        Parameters
        ----------
        id : str
            Patient id
        metadata : Dict[str, str], optional
            Metadata on the document (id, author, reviewer, specialty, etc.)
        scenario : Dict[str, str], optional
            Information on the patient (name, birthdate, sex, etc.)
            providing the writing instructions.
        documents : List[Dict[str, str]], optional
            Documents (id: content) associated with the patient.
        structured_abstract : Dict[str, str], optional
            Structured information on the patient provided by the author at the end
            of the document
        add_diagnostic_codes_to_structured_abstract : bool, optional
            Whether to add diagnostic codes to the structured abstract, by default True
        """
        self.id = (
            id if id is not None else metadata.get("id", None) if metadata else None
        )
        assert self.id is not None, "Patient id must be provided"
        self.metadata = metadata if metadata is not None else {}
        self.scenario = scenario if scenario is not None else {}
        self.documents = documents if documents is not None else []
        self.structured_abstract = (
            structured_abstract if structured_abstract is not None else {}
        )
        self.add_diagnostic_codes_to_structured_abstract = (
            add_diagnostic_codes_to_structured_abstract
        )

    def set_scenario_attribute(self, key: str, value: Any):
        """
        Set a patient scenario attribute. Reject duplicate key with `KeyError`.

        Parameters
        ----------
        key : str
            The attribute name
        value : str
            The attribute value

        Raises
        ------
        KeyError
            If the attribute was already set in the scenario

        """
        if key in self.scenario:
            raise DocumentParsingException(
                str(self.id),
                f"[{self.id}] Attribute '{key}' is already set in the scenario",
            )
        self.scenario[key] = value

    def check_scenario_attribute(self, key: str, value: str):
        """
        Check that a patient scenario attribute has the specified value.

        Parameters
        ----------
        key : str
            The attribute name
        value : str
            The attribute value

        Raises
        ------
        KeyError
            If the attribute was not previously set in the scenario

        ValueError
            If the attribute's value is different than what's expected

        """
        if key not in self.scenario:
            raise DocumentParsingException(
                str(self.id),
                f"[{self.id}] Attribute '{key}' is not set for this patient's scenario",
            )
        if self.scenario[key] != value:
            raise ValueError(
                f"[{self.id}] Attribute '{key}' is '{self.scenario[key]}', not '{value}' as you expect"
            )

    def check_section_header(self, section_header: str) -> str | None:
        """
        Check if a section header is valid for this patient.

        Parameters
        ----------
        section_header : str
            The section header to check.

        Raises
        ------
        KeyError
            If the section header is already stored as a document type.

        NormalizationException
            If the section header cannot be normalized to a known document type.

        Returns
        -------
        str | None
            The normalized report type if the section header is valid, None otherwise.
        """
        if not len(section_header):
            return None
        if section_header in [doc["type"] for doc in self.documents]:
            raise KeyError(f"[{self.id}] Document '{section_header}' is already stored")
        # Match the structured abstract
        if match_structured_abstract(section_header=section_header):
            return "SA"
        # Match the record type
        else:
            record_type = match_record_type(section_header=section_header)
            return record_type

    def add_document(self, normalized_doctype: str, doctype: str, content: str):
        """
        Add a document to the patient's list of documents. Reject duplicate key (normalized doc type) with `KeyError`.
        If the type is a structured abstract ("SA"), parse it and store it as patient's metadata.
        Otherwise, add as a new patient's report.
        Raise KeyError if the doctype is not recognized (doesn't match any known pattern)

        Parameters
        ----------
        normalized_doctype : str
            The normalized type of the document (e.g "CRH", "CRO", etc.)
        doctype : str
            The type of the document (e.g "COMPTE-RENDU D'HOSPITALISATION", etc.)
        content : str
            The textual content of the report

        Raises
        ------
        KeyError
            If the doctype is not recognized (doesn't match any known pattern)

        """
        if normalized_doctype in [doc["type"] for doc in self.documents]:
            raise KeyError(
                f"[{self.id}] Document '{normalized_doctype}' is already stored"
            )
        # if the content is a structured abstract, parse it and store it as patient's metadata
        if normalized_doctype == "SA":
            self.structured_abstract = parse_structured_abstract(
                content, self.add_diagnostic_codes_to_structured_abstract
            )
            return True
        # otherwise it's a regular document (as recognized before)
        else:
            # Match the section header
            self.documents.append(
                {"type": normalized_doctype, "header": doctype, "content": content}
            )
            return True

    def get_id(self) -> str:
        """
        Return patient id

        Returns
        -------
        Dict[str, str]
            The patient id
        """
        return str(self.id)

    def get_documents(self) -> List[Dict[str, str]]:
        """
        Return the patient's reports

        Returns
        -------
        List[Dict[str, str]]
            The patient's reports
        """
        return self.documents

    def extract_reports_to_files(
        self,
        outdir: str,
        overwrite: bool = True,
        word_counter: Optional[WordCounter] = None,
        one_report_per_patient: bool = False,
    ):
        """
        Extract the text of the reports and save them to a specific directory. Create the output directory if needed

        Parameters
        ----------
        outdir : str
            The output directory for the reports
        overwrite: bool
            Whether or not an existing file should be overwritten
        word_count: bool
            Whether to add word count to the document metadata
        one_report_per_patient: bool
            Whether to extract only one report per patient (randomly chosen if multiple reports exist)

        Raises
        ------
        FileExistsError
            If the specific output directory is already a file

        """
        if "specialty" not in self.metadata:
            raise KeyError(f"Specialty is missing from metadata for patient {self.id}")
        subdir = slugify(self.metadata["specialty"], lowercase=False)
        outpath = os.path.join(outdir, subdir)
        if not exists(outpath):
            makedirs(outpath)
        elif not isdir(outpath):
            raise FileExistsError(outpath)

        if one_report_per_patient and len(self.documents) > 1:
            chosen_doc = random.choice(self.documents)
            self.documents = [chosen_doc]

        # local_id: int = 0
        for i, doc in enumerate(self.documents):
            doctype = doc["type"]
            header = doc["header"]
            content = doc["content"]
            # if len(self.documents) == 1:
            filename = f"{self.id}_{doctype}.txt"
            filepath = os.path.join(outpath, f"{filename}")
            # else:
            #     # local_id += 1
            #     filename = f"{doctype}-{local_id}.txt"
            #     filepath = os.path.join(outpath, f"{filename}")
            if exists(filepath) and not overwrite:
                logger.debug(f"{filepath} already exists, skip it")
            with open(filepath, "w") as text_file:
                text = header + "\n\n" + content
                text_file.write(text)

                # Tweak: very few reports (7) contains two pathology reports
                # named "ANAPATH" and "ANAPATH2"
                # We add the suffix "2" to the filename of the second one, to avoid
                # overwriting the first one, but we now change doctype "ANAPATH2"
                # to "ANAPATH" in the metadata, so that both reports are recognized
                # as pathology reports
                if doctype == "ANAPATH2":
                    doctype = "ANAPATH"

                self.documents[i] = {
                    "type": doctype,
                    "header": header,
                    "path": f"{subdir}/{filename}",
                }
                if word_counter is not None:
                    wc = word_counter.count_words(content)
                    self.documents[i]["word_count"] = wc

    def to_dict(self) -> Dict:
        """
        Return a dictionary containing the informations about the patient

        Returns
        -------
        Dict
            A dictionary containing the informations about the patient
        """
        return (
            {"id": self.id}
            | self.metadata
            | {
                "suggested_scenario": self.scenario,
                "documents": self.documents,
                "structured_abstract": self.structured_abstract,
            }
        )

    def __repr__(self) -> str:
        return str(self.to_dict())


def build_file_name(
    specialty: str,
    local_id: str,
    strict: bool,
    extension: str,
    author: Optional[str] = None,
    reviewer: Optional[str] = None,
) -> str:
    """
    Build file name from metadata.
    The file name is specialty-id-author-reviewer.extension
    We can optionally enforce strict mode, which raises an error if author or reviewer are missing.
    Otherwise, they are simply omitted from the file name.

    Parameters
    ----------
    specialty : str
        the specialty of the report
    local_id : str
        the local identifier of the report
    strict : bool
        whether to enforce strict mode for author and reviewer presence
    author : Optional[str], optional
        the trigramme of the author, by default None
    reviewer : Optional[str], optional
        the trigramme of the reviewer, by default None
    extension : str
        the file extension (e.g., "txt", "docx")

    Returns
    -------
    str
        The built file name
    """
    filename = f"{slugify(specialty, lowercase=False)}_{local_id}"
    if author is not None:
        filename += f"_A-{author}"
    elif strict:
        raise ValueError(
            f"Author is required in strict mode for specialty {specialty} and id {local_id}"
        )
    if reviewer is not None:
        filename += f"_R-{reviewer}"
    elif strict:
        raise ValueError(
            f"Reviewer is required in strict mode for specialty {specialty} and id {local_id}"
        )
    filename = f"{filename}.{extension}"
    return filename


def match_record_type(section_header: str) -> str | None:
    """
    Check if the section header matches the pattern for a "record type"

    Parameters
    ----------
        section_header (str): the section header to check

    Returns
    -------
        str: the normalized report type if the section header matches a record type pattern, None otherwise

    Raises
    ------
        NormalizationException
    """
    return report_type_normalization(section_header)


def match_structured_abstract(section_header: str) -> Match[str] | None:
    """
    Check if the section header matches the pattern for a "structured abstract""

    Parameters
    ----------
        section_header (str): the section header to check

    Returns
    -------
        Match[str]: the match object if the section header matches the structured abstract pattern, None otherwise
    """
    return ABSTRACT_PATTERN.match(section_header.upper())


def normalize_structured_abstract_field(label: str, text: str) -> str | dict | None:
    """
    Normalize a structured abstract field using the appropriate cleaning function if any.


    Parameters
    ----------
    label : str
        The structured abstract field label
    text : str
        Raw text from the structured abstract field.

    Returns
    -------
    str | None
        Normalized text (None if the field is empty after normalization)
    """
    # Apply cleaning function if any
    if label in FIELD_CLEANING_FUNCTIONS:
        cleaning_function = FIELD_CLEANING_FUNCTIONS[label]
        return cleaning_function(text)
    # No cleaning function
    else:
        content = text.strip(" -•/.")
        if len(content):
            return content
        else:
            return None


def parse_structured_abstract(text: str, add_diagnostic_codes: bool) -> Dict[str, str]:
    """
    Parse a structured abstract into a dictionary, where each key is the text before a colon (':')
    and the value is the text after the colon, possibly including multiple lines.

    Parameters
    ----------
    text : str
        Input structured text.
    add_diagnostic_codes : bool
        Whether to add diagnostic codes to the structured abstract.

    Returns
    -------
    Dict[str, str]
        Parsed key-value pairs.

    Raises
    ------
    NormalizationException
        when no valid field is found in the structured abstract
    """
    # Normalize text: remove leading/trailing spaces and standardize newlines
    text = text.strip().replace("\r\n", "\n")

    current_pattern = None
    current_text = ""

    structured_abstract: Dict[str, Any] = {}

    for line in text.split("\n"):
        if line.strip() == "":
            continue
        matched = False
        # Sort patterns by length to match the longest first
        for pattern, label in sorted(
            EXPECTED_PATTERNS_IN_STRUCTURED_ABSTRACT.items(),
            key=lambda item: len(item[0].pattern),
            reverse=True,
        ):
            match = pattern.search(line)
            if match:
                if current_pattern is not None and len(current_pattern) > 0:
                    norm_field = normalize_structured_abstract_field(
                        current_pattern, current_text
                    )
                    if norm_field is not None:
                        structured_abstract[current_pattern] = norm_field
                else:
                    if len(current_text.strip()) > 0:
                        raise NormalizationException(
                            f"No valid field found in structured abstract for pattern {current_pattern}, line: '{line.strip()}', current_text: '{current_text}'"
                        )
                current_pattern = label
                if match.group(1) is not None:
                    current_text = match.group(1).strip()
                else:
                    current_text = ""
                matched = True
                break
        if not matched:
            if current_pattern is None:
                raise NormalizationException(
                    f"Line in structured abstract does not match any expected field: '{line}'"
                )
            current_text += "\n" + line

    if current_pattern is not None and len(current_pattern) > 0:
        norm_field = normalize_structured_abstract_field(current_pattern, current_text)

        if norm_field is not None:
            structured_abstract[current_pattern] = norm_field
    else:
        if len(current_text.strip()) > 0:
            raise NormalizationException(
                f"No valid field found in structured abstract for pattern {current_pattern}, end of text"
            )

    if not add_diagnostic_codes:
        # Remove diagnostic codes from structured abstract if any
        for key in [
            "secondary_diagnoses_from_the_list",
            "other_diagnoses",
        ]:
            if key in structured_abstract:
                del structured_abstract[key]
    return structured_abstract


def markdown_to_plain(md_text: str) -> str:
    """
    Call pandoc to convert markdown to plain text
    the format "markdown-smart" instead of "markdown" is necessary to avoid
    smart conversion such as converting straight apostrophes into curly ones.

    Returns
    -------
    str
        The plain text version of the specified Markdown text
    """
    return pypandoc.convert_text(
        md_text, format="markdown-smart", to="plain", extra_args=["--wrap=none"]
    )


def parse_patient_document(
    docx_path: str,
    metadata: Optional[Dict[str, str]] = None,
    add_diagnostic_codes_to_structured_abstract: bool = True,
) -> Patient:
    """
    Extracts sections from a .docx file using 'Heading 2' style as section delimiters.
    Removes all formatting and returns plain text.

    Steps:

    # 1. If metadata is not provided, extract them from path
    2. Convert docx to markdown in order to simplify section extraction
    3. Build sections based on "Heading 2" ("##")
        - The first chunk is the automatically-built introduction:
          description of the scenario and instructions (see step 5)
        - The following sections are the reports (generally one report but we can up to 3)
        - Optionally, a last section contains a structured abstract
        If "##" section headers do not match any of these items, then they are
        considered as regular text
    4. Within each section, we are only interested in the plain
        text, so we convert markdown to plain text at this stage
    5. Parse the scenario (sanity check against previously known metadata)
    6. Sanity checks

    Parameters
    ----------
    docx_path : str
        Path to the .docx file.
    metadata : Optional[Dict[str, str]], optional
        Metadata on the document (id, author, reviewer, specialty, etc.),
        by default None
    add_diagnostic_codes_to_structured_abstract : bool, optional
        Whether to add diagnostic codes to the structured abstract, by default True

    Returns
    -------
    Patient
        A Patient object containing all information (metadata + reports)

    Raises
    ------
    InvalidPathException
        If the path doesn't match the expected pattern
    DocumentParsingException
        If the parsing of a docx document fails
    """
    # 1. Extract document metadata from path
    # doc_id, path_metadata = path_parser(docx_path, filter=filter)

    # 2. Convert docx to markdown
    md: str = pypandoc.convert_file(
        source_file=docx_path,
        to="md",
        # to="plain",
        extra_args=("--standalone", "--wrap=none"),
        # outputfile=output_path,
    )

    patient = Patient(
        metadata=metadata,
        add_diagnostic_codes_to_structured_abstract=add_diagnostic_codes_to_structured_abstract,
    )
    scenario_md: list[str] = []
    report_buffer: list[str] = []
    current_section = None
    current_section_normalized = None

    # 3, 4
    for line in md.split("\n"):
        # New section = start a new document
        # only if the section header matches a registered section header expression
        if line.startswith(SECTION_STYLE):
            # If the line contains more than just "##"
            # check if it's a recognized section header
            if len(line) > 4:
                # HACK to correct "Compte de passage" to "Compte rendu de passage"
                # (common typo in obstetrics reports)
                if line.startswith("## Compte de passage"):
                    line = "## Compte rendu de passage" + line[20:]
                try:
                    record_type = patient.check_section_header(line.strip())
                except NormalizationException as e:
                    logger.warning(f"[{patient.get_id()}] {str(e)}")
                    record_type = None

                # I removed logging of unrecognized section headers
                # because many reports contains custom section headers
                # that are not relevant to the document structure
                # and I have now other ways to check the sanity of the document structure
                # if record_type is None:
                #     if current_section is None:
                #         # Not a recognized section header -> continue the scenario
                #         logger.error(
                #             f"[{patient.get_id()}] Unrecognized section header outside any document: '{line}'"
                #         )
                #     else:
                #         logger.warning(
                #             f"[{patient.get_id()}] Unrecognized section header '{line}'"
                #         )
            else:
                record_type = None

        else:
            record_type = None
        #     # Looking for a section header even if it does not start with "##"
        #     record_type = patient.check_section_header(line.strip())
        #     if record_type is not None:
        #         logger.warning(
        #             f"[{patient.get_id()}] Section header without expected style: '{line}'"
        #         )
        # If the line is a recognized section header
        if record_type is not None:
            logger.debug(
                f"[{patient.get_id()}] Found section header: '{line}' -> '{record_type}'"
            )
            # store previous document
            # after conversion into plan text
            if current_section:
                # Try to add a new document
                assert current_section_normalized is not None
                patient.add_document(
                    normalized_doctype=current_section_normalized,
                    doctype=current_section,
                    content=markdown_to_plain("\n".join(report_buffer).strip()),
                )
            current_section = markdown_to_plain(line).strip()
            current_section_normalized = record_type
            report_buffer = []
        # Not a recognized section header -> continue the current document
        else:
            # If we are not in a section, this is part of the scenario
            if current_section:
                report_buffer.append(line)
            else:
                scenario_md.append(line)

    # Add last section (end of document)
    if current_section:
        assert current_section_normalized is not None
        patient.add_document(
            normalized_doctype=current_section_normalized,
            doctype=current_section,
            content=markdown_to_plain("\n".join(report_buffer).strip()),
        )

    plain_scenario = markdown_to_plain("\n".join(scenario_md).strip())

    # 5. Parse scenario (everything before the first section header)
    for line in plain_scenario.split("\n"):
        for pattern, label in EXPECTED_PATTERNS_IN_SCENARIO.items():
            match = pattern.search(line)
            if match:
                value = match.group(1)
                if value is None:
                    value = ""
                # Apply cleaning function if any
                if label in FIELD_CLEANING_FUNCTIONS:
                    cleaning_function = FIELD_CLEANING_FUNCTIONS[label]
                    cleaned_value = cleaning_function(value.strip())
                # No cleaning function
                else:
                    cleaned_value = value.strip()
                    if len(cleaned_value) == 0:
                        cleaned_value = None
                if cleaned_value is not None:
                    patient.set_scenario_attribute(label, cleaned_value)
                break

    # 6. Sanity checks
    documents = patient.get_documents()
    if len(documents) == 0:
        logger.error(f"[{patient.get_id()}] No document found in the file")
    if metadata is not None:
        if "primary_diagnosis" not in patient.scenario:
            logger.error(
                f"[{patient.get_id()}] primary_diagnosis is missing from the scenario"
            )
        # Check that category ("CRH", "CRO", "CRH+CRO") matches report types found in the document
        if "category" in metadata:
            expected_category = metadata["category"]
            types_in_document = [doc["type"] for doc in documents]
            if len(documents) == 0:
                logger.error(
                    f"[{patient.get_id()}] No document found but expected category {expected_category}"
                )
            if expected_category == "CRH+CRO":
                if len(types_in_document) > 3:
                    logger.error(
                        f"[{patient.get_id()}] Expecting no more than 3 documents for category {expected_category} but found {types_in_document}"
                    )
                # both CRO and CRH must be present
                for cat in ["CRH", "CRO"]:
                    if cat not in types_in_document:
                        logger.error(
                            f"[{patient.get_id()}] Expected {cat} in document types but not found"
                        )
            elif expected_category == "CRH":
                # CRC instead of CRH: fine
                if len(types_in_document) == 1 and types_in_document[0] == "CRC":
                    pass
                # ANAPATH instead of CRH: fine
                elif len(types_in_document) == 1 and types_in_document[0] == "ANAPATH":
                    pass
                # ANAPATH + ANAPATH2 instead of CRH: fine
                elif len(types_in_document) == 2 and all(
                    [t in ["ANAPATH", "ANAPATH2"] for t in types_in_document]
                ):
                    pass
                # otherwise: error if not exactly one CRH
                elif not all([t.startswith("CRH") for t in types_in_document]):
                    logger.warning(
                        f"[{patient.get_id()}] Expected exactly 1 document of category {expected_category} but found {types_in_document}"
                    )
            elif expected_category == "CRO":
                if len(types_in_document) != 3:
                    logger.warning(
                        f"[{patient.get_id()}] Expected exactly 3 documents for category {expected_category} but found {types_in_document}"
                    )
                for cat in ["CRH", "CRO", "CRC"]:
                    if cat not in types_in_document:
                        logger.warning(
                            f"[{patient.get_id()}] Expected a document of category {cat} but found {types_in_document}"
                        )
            else:
                logger.error(
                    f"[{patient.get_id()}] Unknown expected category: {expected_category}"
                )
        if "specialty" in metadata:
            # Check that all required scenario fields are present in the patient scenario
            for field in EXPECTED_PATTERNS_IN_SCENARIO.values():
                # missing type_of_care or "primary_procedure" in ANATOMOPATHOLOGIE specialty: fine
                if (
                    field in ["type_of_care", "primary_procedure"]
                    and metadata["specialty"] == "ANATOMOPATHOLOGIE"
                ):
                    continue
                # missing primary_procedure in CANCERO-ADULTE specialty: fine
                if field == "primary_procedure" and metadata["specialty"] in [
                    "CANCERO ADULTE",
                    "CARDIOLOGIE",
                    "CHIR ORTHO ET TRAUMATO",
                    "CHIR.CARDIO-VASC.",
                    "CHIRURGIE VISCERALE",
                    "GYNECOLOGIE",
                    "HEMATOLOGIE CLINIQUE",
                    "HEPATO-GASTRO-ENTERO",
                    "MALADIES INFECTIEUSES",
                    "MEDECINE GERIATRIQUE",
                    "MEDECINE INTER-SPECIALITES",
                    "MEDECINE INTERNE",
                    "MEDECINE PEDIATRIQUE",
                    "NEPHROLOGIE",
                    "NEUROLOGIE",
                    "OBSTETRIQUE",
                    "PNEUMOLOGIE",
                    "REANIMATION",
                    "UROLOGIE",
                ]:
                    continue
                # any missing field in CANCERO-ADULTE specialty, if the report contains "Réponse au traitement": fine
                if metadata["specialty"] == "CANCERO ADULTE":
                    fine = False
                    for doc in documents:
                        if "Réponse au traitement" in md:
                            fine = True
                            break
                    if fine:
                        continue
                # These ones have been checked manually
                if metadata["id"] in ["GYNECOLOGIE-00075"]:
                    continue
                # Else, all missing fields are errors
                if field not in patient.scenario:
                    logger.error(
                        f"[{patient.get_id()}] (specialty {metadata['specialty']}) Missing scenario field: {field}"
                    )
    # Delete metadata["category"] because it's meaningless after parsing
    if metadata is not None and "category" in metadata:
        del metadata["category"]
    logger.info(f"Parsed document {docx_path} for patient ID {patient.get_id()}")
    return patient


class GoogleDriveDownloader:
    """Utility class to download files from Google Drive."""

    # Pattern for link such as https://drive.google.com/open?id=1BiLQKVpNiGkephDUpepQxSt-Kyfnth94&usp=drive_copy
    FILE_ID_PATTERN = r"https://drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)(?:&\S*)?"

    @staticmethod
    def get_file_id_from_link(link: str) -> str:
        """
        Extract the file ID from a Google Drive link.

        Parameters
        ----------
        link : str
            The Google Drive link.

        Returns
        -------
        Optional[str]
            The extracted file ID, or None if not found.
        """
        import re

        match = re.match(GoogleDriveDownloader.FILE_ID_PATTERN, link)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Could not extract file ID from link: {link}")

    def __init__(self, credential_file: str):
        """
        Parameters
        ----------
        credential_file : str
            Path to the Google API credentials file.
        """
        # OAuth scope for read-only access
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

        # Authenticate with your Google account
        flow = InstalledAppFlow.from_client_secrets_file(credential_file, SCOPES)
        creds = flow.run_local_server(port=0)

        # Build the Drive service
        self.service = build("drive", "v3", credentials=creds)

    def download_google_drive_report(self, file_id: str, destination: str) -> bool:
        """
        Download a file from Google Drive given its file ID.

        Parameters
        ----------
        file_id : str
            The Google Drive file ID.
        destination : str
            The local path where to save the downloaded file.

        Returns
        -------
        bool
            True if the file was downloaded successfully.
        """
        # Request the file
        # file = (
        #     self.service.files()
        #     .get(fileId=file_id, fields="name", supportsAllDrives=True)
        #     .execute()
        # )
        # filename = file["name"]

        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.FileIO(destination, "wb")
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        logger.debug(f"File downloaded: {destination}")
        return True


def document_generator(cfg: Dict):
    """Generate document file paths based on configuration.
    Two modes:
    1. If no metadata file is provided, scan all .docx files in the input directory.
    2. If a metadata file is provided, read the metadata to find relevant documents.

    Parameters
    ----------
        cfg (Dict): Configuration dictionary.

    Yields
    ------
        Tuple[str, Dict[str, str]]: Yields a pair containing the file path and a dictionary containing metadata.
    """
    input_mode = cfg["input_mode"]
    overwrite = cfg.get("overwrite", False)
    gdd = None

    if input_mode == "local":
        remote_file_access = False
        metadata_file = None
        filter_fn = None
    elif input_mode == "Google drive":
        remote_file_access = True
        filter = cfg["drive_mode"].get("filter", None)
        if filter is not None:
            filter_fn = globals().get(filter, None)
            if filter_fn is None:
                raise ValueError(f"Unknown filter function: {filter}")
            logger.info(f"Using filter function: {filter}")
        else:
            filter_fn = None
        metadata_file = cfg["drive_mode"].get("metadata_file", None)
        if metadata_file is None and remote_file_access:
            raise ValueError(
                "When input_mode is 'Google drive', metadata_file must be provided in the config."
            )
        else:
            logger.info(f"Using metadata file: {metadata_file}")
    else:
        raise ValueError(f"Unknown input_mode: {input_mode}")

    # In "local" mode, this is the directory where to look for reports -> should exist
    # In "Google drive" mode, the downloaded reports will be stored temporarily here -> should not exist or be empty
    if remote_file_access:
        in_directory = cfg["in_directory"]
        # Check that in_directory does not exist or is empty
        if os.path.exists(in_directory) and os.listdir(in_directory):
            if overwrite:
                logger.info(f"Will delete content from {in_directory}")
                shutil.rmtree(in_directory)
            else:
                logger.info(f"Will keep already existing files in {in_directory}")
        # Create the directory if it does not exist
        os.makedirs(in_directory, exist_ok=True)
        google_credentials_file = cfg["drive_mode"]["google_credentials_file"]
    else:
        in_directory = cfg["in_directory"]
        google_credentials_file = None
        logger.debug(f"Using local file access in directory: {in_directory}")

        if not os.path.exists(in_directory):
            # try relative to this notebook folder
            in_directory = os.path.join(
                os.path.dirname(os.path.abspath("__file__")), in_directory
            )

    if metadata_file is None:
        assert (
            in_directory is not None
        ), "in_directory must be provided in the config when no metadata_file is given."
        logger.debug(
            f"No metadata file provided, scanning all documents in {in_directory}."
        )
        for root, _, files in os.walk(in_directory):
            for file_name in files:
                if file_name.lower().endswith(".docx"):
                    file_path = os.path.join(root, file_name)
                    try:
                        local_id, specialty, other_metadata = path_parser(file_name)
                    except InvalidPathException as e:
                        logger.error(e.message)
                        local_id, specialty, other_metadata = (-1, "UNKNOWN", {})
                    global_id = f"{slugify(specialty, lowercase=False)}-{local_id}"
                    yield file_path, {
                        "id": global_id,
                        "local_id": local_id,
                        "specialty": specialty,
                    } | other_metadata
    else:
        if not os.path.exists(metadata_file):
            # try relative to this notebook folder
            metadata_file = os.path.join(
                os.path.dirname(os.path.abspath("__file__")), metadata_file
            )
        logger.debug(f"Loading metadata from {metadata_file}")
        doc_link_column_name = cfg["drive_mode"]["doc_link_column_name"]
        specialty_column_name = cfg["drive_mode"]["specialty_column_name"]
        id_column_name = cfg["drive_mode"]["id_column_name"]
        author_column_name = cfg["drive_mode"]["author_column_name"]
        reviewer_column_name = cfg["drive_mode"]["reviewer_column_name"]
        category_column_name = cfg["drive_mode"]["category_column_name"]
        pool_column_name = cfg["drive_mode"].get("pool_column_name", None)
        split_column_name = cfg["drive_mode"].get("split_column_name", None)
        comments_column_name = cfg["drive_mode"].get("comments_column_name", None)
        tag_reject_reason_column_name = cfg["drive_mode"].get(
            "tag_reject_reason_column_name", None
        )

        wb = openpyxl.load_workbook(metadata_file, data_only=True)
        sheets = wb.sheetnames
        ws = wb[sheets[0]]
        ws.rows
        doc_link_col_idx = 0
        specialty_col_idx = 0
        id_idx = 0
        author_col_idx = 0
        reviewer_col_idx = 0
        category_col_idx = 0
        pool_col_idx = -1
        split_col_idx = -1
        comments_col_idx = -1
        tag_reject_reason_col_idx = -1

        # n = 0

        for i, row in enumerate(ws.rows):
            # Headers
            if i == 0:
                headers = [cell.value for cell in row]
                doc_link_col_idx = headers.index(doc_link_column_name)
                specialty_col_idx = headers.index(specialty_column_name)
                id_idx = headers.index(id_column_name)
                author_col_idx = headers.index(author_column_name)
                reviewer_col_idx = headers.index(reviewer_column_name)
                category_col_idx = headers.index(category_column_name)
                if pool_column_name is not None:
                    try:
                        pool_col_idx = headers.index(pool_column_name)
                    except ValueError:
                        pool_col_idx = -1
                else:
                    pool_col_idx = -1
                if split_column_name is not None:
                    try:
                        split_col_idx = headers.index(split_column_name)
                    except ValueError:
                        split_col_idx = -1
                else:
                    split_col_idx = -1
                if comments_column_name is not None:
                    try:
                        comments_col_idx = headers.index(comments_column_name)
                    except ValueError:
                        comments_col_idx = -1
                else:
                    comments_col_idx = -1
                if tag_reject_reason_column_name is not None:
                    try:
                        tag_reject_reason_col_idx = headers.index(
                            tag_reject_reason_column_name
                        )
                    except ValueError:
                        tag_reject_reason_col_idx = -1
                else:
                    tag_reject_reason_col_idx = -1
            else:
                cells = list(row)
                doc_link = cells[doc_link_col_idx]
                local_id = str(cells[id_idx].value)
                specialty = unidecode(
                    str(cells[specialty_col_idx].value).strip().upper()
                )
                global_id = f"{slugify(specialty, lowercase=False)}-{local_id}"
                doc_name = str(doc_link.value).split("/")[-1]
                if filter_fn is None:
                    filter_result = FilterOutcome.ACCEPT_STRICT  # noqa: F405
                else:
                    filter_result = filter_fn(cells)
                # Apply filter function if any (e.g., to only select documents with "relu" in the name)
                if filter_result != FilterOutcome.REJECT:  # noqa: F405
                    # if str(status).strip().lower() == "relu" or filter == "none":
                    # n += 1
                    # if n < 1561:
                    #     yield None, None, None
                    #     continue

                    assert (
                        doc_link.hyperlink is not None
                    ), f"No hyperlink found in row {i+1}"
                    assert (
                        doc_link.value is not None
                    ), f"No hyperlink value found in row {i+1}"
                    doc_name = str(doc_link.value).split("/")[-1]
                    author = cells[author_col_idx].value
                    reviewer = cells[reviewer_col_idx].value
                    # Author and reviewer must be a 3-character string
                    if author is not None:
                        author = str(author).strip().upper()
                        if len(author) != 3:
                            logger.error(
                                f"{global_id} -- Author '{author}' is not a 3-character string"
                            )
                    else:
                        logger.error(f"{global_id} -- Author is None")
                    if reviewer is not None:
                        reviewer = str(reviewer).strip().upper()
                        if len(reviewer) != 3:
                            logger.error(
                                f"{global_id} -- Reviewer '{reviewer}' is not a 3-character string"
                            )
                    else:
                        logger.error(f"{global_id} -- Reviewer is None")
                    category = cells[category_col_idx].value
                    if category not in ("CRH", "CRO", "CRH+CRO"):
                        logger.error(
                            f"{global_id} -- Category '{category}' is not one of 'CRH', 'CRO', 'CRH+CRO'"
                        )
                    filename = build_file_name(
                        specialty=specialty,
                        local_id=local_id,
                        author=author,
                        reviewer=reviewer,
                        strict=filter_result
                        == FilterOutcome.ACCEPT_STRICT,  # noqa: F405
                        extension="docx",
                    )
                    extra_args = {}
                    if pool_col_idx >= 0:
                        pool = cells[pool_col_idx].value
                        if pool is not None:
                            pool = str(pool).strip()
                            if pool not in USE_CASE_NAMES:
                                raise ValueError(
                                    f"{global_id} -- Pool '{pool}' is not in the list of recognized use cases: {USE_CASE_NAMES}"
                                )
                            pool = USE_CASE_NAMES[pool]
                            if split_col_idx >= 0:
                                split = cells[split_col_idx].value
                                if split is not None:
                                    split = str(split).strip()
                                    if split.upper() == "TEST":
                                        split = "TEST"
                                        pool = f"{pool}_{split}"
                            extra_args["pool"] = pool
                    if comments_col_idx >= 0:
                        comments = cells[comments_col_idx].value
                        if comments is not None:
                            comments = str(comments).strip()
                            if len(comments) > 0:
                                extra_args["comments"] = comments
                    if tag_reject_reason_col_idx >= 0:
                        tag_reject_reason = cells[tag_reject_reason_col_idx].value
                        if tag_reject_reason is not None:
                            tag_reject_reason = str(tag_reject_reason).strip()
                            if len(tag_reject_reason) > 0:
                                extra_args["tag_reject_reason"] = tag_reject_reason
                    # match = FILEPATH_PATTERN.match(doc_name)
                    # if match:
                    # patient_id_in_specialty = str(match.group(3))

                    found: List[str] = []
                    if not remote_file_access:
                        # Local file access
                        assert (
                            in_directory is not None
                        ), "in_directory must be provided in the config."
                        dir_name = os.path.join(in_directory, specialty)
                        if not os.path.isdir(dir_name):
                            logger.error(
                                f"Directory {dir_name} does not exist. Skipping document {doc_name}."
                            )
                            continue

                        logger.debug(
                            f"Searching for document {doc_name} under specialty {specialty}."
                        )
                        for root, _, files in os.walk(dir_name):
                            for file_name in files:
                                if (
                                    "relu" in file_name.lower()
                                    and local_id in file_name
                                ):
                                    file_path = os.path.join(root, file_name)
                                    found.append(file_path)
                    else:
                        # Remote file access (Google Drive)
                        assert (
                            doc_link.hyperlink.target is not None
                        ), f"No hyperlink target found in row {i+1}"
                        logger.debug(
                            f"Searching for document {doc_link.hyperlink.target} in Google Drive."
                        )
                        try:
                            file_id = GoogleDriveDownloader.get_file_id_from_link(
                                doc_link.hyperlink.target
                            )
                        except ValueError:
                            logger.error(
                                f"[{global_id}] -- Could not extract file ID from link: {doc_link.hyperlink.target}"
                            )
                            continue
                        # Create a destination subdirectory for the specialty if it does not exist
                        specialty_dir = os.path.join(
                            in_directory, slugify(specialty, lowercase=False)
                        )
                        os.makedirs(specialty_dir, exist_ok=True)
                        # Download the file
                        destination = join(specialty_dir, filename)
                        if exists(destination) and not overwrite:
                            logger.debug(f"File already exists: {destination}")
                            found.append(destination)
                        else:
                            # Only initialize the downloader when needed
                            # (because it requires user authentication)
                            if gdd is None:
                                assert (
                                    google_credentials_file is not None
                                ), "google_credentials_file must be provided in the config"
                                gdd = GoogleDriveDownloader(google_credentials_file)

                            try:
                                if gdd.download_google_drive_report(
                                    file_id,
                                    destination=destination,
                                ):
                                    found.append(destination)
                            except Exception as e:
                                logger.error(
                                    f"[{global_id}] -- Error downloading file with ID {file_id} to destination {destination}, from Google Drive: {str(e)}"
                                )
                                if os.path.exists(destination):
                                    os.remove(
                                        destination
                                    )  # Remove the file if it was partially downloaded
                    if not len(found):
                        logger.error(
                            f"{global_id} -- No file found for patient ID {local_id} in specialty {specialty}."
                        )
                        raise ValueError()
                    elif len(found) > 1:
                        logger.error(
                            f"{global_id} -- Multiple files found for patient ID {local_id} in specialty {specialty}. \n {"\n".join(found)} "
                        )
                        raise ValueError()
                    else:
                        yield found[0], {
                            "id": global_id,
                            "local_id": local_id,
                            "specialty": specialty,
                            "author": author,
                            "reviewer": reviewer,
                            "category": category,
                        } | extra_args
                    # else:
                    #     logger.error(f"{global_id} -- Pattern did not match for file name {doc_name}")
                    # raise ValueError()
                else:
                    logger.debug(f"{global_id} does not pass the filter -> skip")


def build_json_output_header(config: Dict) -> Dict:
    """
    Build the JSON output header based on the configuration.

    Parameters
    ----------
    config : Dict
        Configuration dictionary.

    Returns
    -------
    Dict
        The JSON output header.
    """
    json_header = {
        "name": config["dataset_name"],
        "version": config["dataset_version"],
        "licenses": config["dataset_licenses"],
        "license_urls": config["dataset_license_urls"],
        "description": config["dataset_description"],
    }
    return json_header
