import shutil
import zipfile

from huggingface_hub import HfApi, RepoCard
from huggingface.parhaf import Parhaf
import tempfile
from collections import defaultdict
import json
from datasets import DatasetBuilder
from reports_extractor.normalization import MEDICAL_SPECIALTIES_FR_EN
import os
from typing import Any, Dict, Iterable, List, Tuple
from slugify import slugify
import logging
import re
import yaml

logger = logging.getLogger("publication")


def get_markdown_statistics(
    json_path: str,
    lang: str = "EN",
    translation_map: Dict[str, str] | None = None,
) -> str:
    """
    Build a Markdown pivot table from a JSON dataset containing medical items.

    The table contains:
        - rows    : specialty
        - columns : pool
        - cells   : number of occurrences

    Parameters
    ----------
    json_path : str
        Path to the input JSON file.
        The JSON must contain a root key "data" with iterable elements
        containing at least:
            - "specialty"
            - "pool"

    lang : {"FR", "EN"}, default="FR"
        If "EN", specialties are translated using `translation_map`.

    translation_map : dict[str, str] or None, optional
        Mapping from French specialty to English specialty.
        Ignored if lang != "EN".

    Returns
    -------
    str
        A Markdown formatted table.

    Examples
    --------
    >>> md = json_specialty_pool_to_markdown("patients.json")
    >>> print(md)
    | Specialty | A | B |
    |---|---|---|
    | Cardiology | 12 | 4 |
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    specialties: set[str] = set()
    pools: set[str] = set()
    doc_number = 0
    word_number = 0
    patient_number = len(data["data"])

    for item in data["data"]:
        specialty: str = item["specialty"]
        pool: str = item["pool"]

        if lang == "EN" and translation_map is not None:
            specialty = translation_map[specialty]

        counts[specialty][pool] += 1
        specialties.add(specialty)
        pools.add(pool)
        doc_number += len(item.get("documents", []))
        for doc in item.get("documents", []):
            word_number += doc["word_count"]

    sorted_specialties = sorted(specialties)
    # Sort pools with "General" first if it exists, then alphabetically
    if "General" in pools:
        sorted_pools = ["General"] + sorted(p for p in pools if p != "General")
    else:
        sorted_pools = sorted(pools)

    # Number of patients, documents, words
    # Markdown table with one row and two columns
    stats_md = f"##### Main statistics \n\n| Patients | Documents | Words |\n|---|---|---|\n| {patient_number} | {doc_number} | {word_number} |"

    # Patient per specialty
    spe_md = "##### Patient count per specialty\n\n" + _pivot_to_markdown(
        counts, sorted_specialties, sorted_pools
    )
    return stats_md + "\n\n" + spe_md


def _pivot_to_markdown(
    counts: Dict[str, Dict[str, int]],
    specialties: Iterable[str],
    pools: Iterable[str],
) -> str:
    """
    Convert a nested counting dictionary into a Markdown table.

    Parameters
    ----------
    counts : dict[str, dict[str, int]]
        Nested dictionary containing counts[rows][columns].
    specialties : Iterable[str]
        Row labels.
    pools : Iterable[str]
        Column labels.

    Returns
    -------
    str
        Markdown table string.
    """

    header = ["Specialty", *pools, "Total"]

    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]

    for spec in specialties:
        row = [spec] + [str(counts[spec].get(pool, 0)) for pool in pools]
        total = sum(counts[spec].values())
        row.append(f"**{str(total)}**")
        lines.append("| " + " | ".join(row) + " |")

    # Final total for each column and overall total
    total_row = ["**Total**"]
    overall_total = 0
    for pool in pools:
        pool_total = sum(counts[spec].get(pool, 0) for spec in specialties)
        total_row.append(f"**{pool_total}**")
        overall_total += pool_total
    total_row.append(str(overall_total))
    lines.append("| " + " | ".join(total_row) + " |")

    return "\n".join(lines)


def generate_md_toc(markdown: str, min_level=2, max_level=3) -> Tuple[str, str]:
    """
    Generate a table of contents and inject section IDs into a markdown document.

    IDs are based on the section numbering when available.

    Parameters
    ----------
    markdown : str
        Input markdown document.
    min_level : int, optional
        Minimum heading level to include in the TOC (default is 2, which corresponds to "##").
    max_level : int, optional
        Maximum heading level to include in the TOC (default is 3, which corresponds to "###").

    Returns
    -------
    Tuple[str, str]
        (modified_markdown, toc_markdown)
    """
    lines = markdown.splitlines()
    toc_entries: List[str] = []
    new_lines: List[str] = []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)")

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            hashes, title = match.groups()
            level = len(hashes)

            if level < min_level or level > max_level:
                new_lines.append(line)
                continue

            section_id = slugify(title)

            # Remove existing {#id} if present
            title_clean = re.sub(r"\s*\{#.*\}$", "", title)

            # Add ID to heading
            new_heading = f"{hashes} {title_clean} "  # {{#{section_id}}}"
            new_lines.append(new_heading)

            # Build TOC entry
            indent = "  " * (level - min_level)
            toc_entries.append(f"{indent}- [{title_clean}](#{section_id})")

        else:
            new_lines.append(line)

    toc_markdown = "## Table of Contents \n\n" + "\n".join(toc_entries)
    modified_markdown = "\n".join(new_lines)

    return modified_markdown, toc_markdown


def create_README_from_builder(
    builder: DatasetBuilder,
    json_corpus_file: str,
    readme_template_file: str,
    changelog_file: str,
    hf_dataset_name: str,
    paper_url: str,
    split_description: str,
):

    with open(readme_template_file, "r") as f:
        readme_content = f.read()

    with open(changelog_file, "r") as f:
        changelog_content = f.read()

    statistics_md = get_markdown_statistics(
        json_corpus_file, lang="EN", translation_map=MEDICAL_SPECIALTIES_FR_EN
    )

    # Get short name from dataset name (after the slash)
    if "/" in hf_dataset_name:
        _, hf_ds_name = hf_dataset_name.split("/")
    else:
        raise ValueError(
            f"Invalid dataset name {hf_dataset_name}, expected format 'ORG/NAME'"
        )

    # Replace the placeholder with the YAML block
    readme_content = readme_content.replace(
        "{{YAML_tags}}",
        yaml.safe_dump(
            builder.info._to_yaml_dict(), sort_keys=False, allow_unicode=True
        ),
    )
    readme_content = readme_content.replace("{{CHANGELOG}}", changelog_content)
    readme_content = readme_content.replace("{{dataset_shortname}}", hf_ds_name)
    readme_content = readme_content.replace(
        "{{dataset_split_description}}", split_description
    )
    readme_content = readme_content.replace("{{dataset_name}}", hf_dataset_name)
    readme_content = readme_content.replace("{{paper_url}}", paper_url)
    readme_content = readme_content.replace("{{corpus_statistics}}", statistics_md)

    readme_content = readme_content.replace("{{json_corpus_file}}", json_corpus_file)
    readme_content, toc_content = generate_md_toc(readme_content)
    readme_content = readme_content.replace("{{TABLE_OF_CONTENTS}}", toc_content)

    return readme_content


def publish_dataset(
    raw_data_dir: str,
    json_corpus_file: str,
    cfg: Dict[str, Any],
):
    """
    Publish the dataset to HuggingFace, including both the structured dataset (parquet/arrow)
    and the standalone data (JSON + text files).
    Create the README card with dataset information and statistics.

    Parameters
    ----------
    raw_data_dir : str
        Path to the directory containing the original text files of the reports.
    json_corpus_file : str
        Path to the output JSON file generated by the reports extractor.
    cfg : Dict[str, Any]
        Configuration dictionary
    """
    # Publish HuggingFace (parquet/arrow) dataset
    logger.info(f"Publishing HuggingFace dataset from {json_corpus_file}...")
    hf_dataset_name = cfg["hf_dataset_name"]
    hf_extra_data_dir = cfg.get("hf_data_directory", None)
    builder = Parhaf(json_corpus_file, cfg)
    builder.download_and_prepare()
    ds = builder.as_dataset()
    ds.push_to_hub(hf_dataset_name, commit_message="v" + str(builder.version()))

    # Publish standalone data in a separate directory
    logger.info(
        f"Publishing standalone data (JSON + text files) to HuggingFace dataset {hf_dataset_name}..."
    )
    standalone_data_dir = "standalone"
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create directory inside temporary directory
        standalone_data_path = os.path.join(tmpdirname, standalone_data_dir)
        os.makedirs(standalone_data_path, exist_ok=True)
        # Copy the JSON file to the standalone data path
        shutil.copy(
            json_corpus_file,
            os.path.join(standalone_data_path, os.path.basename(json_corpus_file)),
        )
        # Zip the text files and copy to the data directory
        #
        logger.info(f"Creating zip file for text documents in {raw_data_dir}...")
        with zipfile.ZipFile(
            os.path.join(standalone_data_path, "data.zip"), "w"
        ) as zipf:
            for d in os.listdir(raw_data_dir):
                if os.path.isdir(os.path.join(raw_data_dir, d)):
                    for f in os.listdir(os.path.join(raw_data_dir, d)):
                        if f.endswith(".txt"):
                            logger.debug(f"Adding {os.path.join(d, f)} to zip file...")
                            zipf.write(
                                os.path.join(raw_data_dir, d, f),
                                arcname=os.path.join(d, f),
                            )
        api = HfApi()
        logger.info(f"Uploading standalone data {standalone_data_path} ...")
        api.upload_folder(
            folder_path=standalone_data_path,
            path_in_repo=standalone_data_dir,
            repo_id=hf_dataset_name,
            repo_type="dataset",
        )

    # If a separate data directory is specified in the config, upload its contents as well
    if hf_extra_data_dir is not None:
        logger.info(f"Uploading extra content from {hf_extra_data_dir} ...")
        # Parse the directory and upload its contents to HuggingFace
        for elem in os.listdir(hf_extra_data_dir):
            elem_path = os.path.join(hf_extra_data_dir, elem)
            if os.path.isfile(elem_path):
                logger.info(f"Uploading file {elem_path} ...")
                api.upload_file(
                    path_or_fileobj=elem_path,
                    path_in_repo=elem,
                    repo_id=hf_dataset_name,
                    repo_type="dataset",
                )
            elif os.path.isdir(elem_path):
                logger.info(f"Uploading folder {elem_path} ...")
                api.upload_folder(
                    folder_path=elem_path,
                    path_in_repo=elem,
                    repo_id=hf_dataset_name,
                    repo_type="dataset",
                )

    # Create Card (README)
    logging.info("Creating README for HuggingFace dataset...")
    readme_template_file = cfg["readme_template_file"]
    changelog_file = cfg["changelog_file"]
    hf_dataset_name = cfg["hf_dataset_name"]
    paper_url = cfg["paper_url"]
    split_description = cfg["dataset_split_description"]
    # output_readme_file = os.path.join(hf_dataset_directory, "README.md")

    readme_text = create_README_from_builder(
        builder=builder,
        json_corpus_file=json_corpus_file,
        readme_template_file=readme_template_file,
        changelog_file=changelog_file,
        hf_dataset_name=hf_dataset_name,
        paper_url=paper_url,
        split_description=split_description,
    )
    card = RepoCard(readme_text)
    card.push_to_hub(hf_dataset_name, repo_type="dataset")
