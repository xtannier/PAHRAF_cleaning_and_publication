# PARHAF Fictional Report Extraction

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-CC%20BY%204.0%20%7C%20Etalab%202.0-green)
![Python](https://img.shields.io/badge/python-3.10%2B-informational)

Toolkit to extract, normalize, and package PARHAF fictional French clinical reports from `.docx` sources into:

- a standalone corpus (`patients.json` + per-report `.txt` files), and
- a Hugging Face dataset representation when enabled.

The project is notebook-driven (`extract_reports.ipynb`) and built around reusable Python modules in `reports_extractor/`.


## What This Project Does

This repository processes synthetic clinical reports from the PARTAGES initiative.

Main workflow:

1. Load extraction configuration from `config/config.yaml`.
2. Discover source `.docx` files:
   - from local folders, or
   - from Google Drive links listed in an Excel metadata file.
3. Parse and normalize content (scenario metadata, report type, structured abstract, diagnostics/procedures).
4. Export plain text reports by specialty and aggregate patient-level metadata into `patients.json`.
5. Optionally publish both structured and standalone artifacts to Hugging Face.

Core implementation:

- parsing/generation: `reports_extractor/utils.py`
- normalization rules: `reports_extractor/normalization.py`
- metadata filters: `reports_extractor/filters.py`
- publishing and dataset card generation: `reports_extractor/publication.py`
- Hugging Face dataset builder: `huggingface/parhaf.py`

## Why This Project Is Useful

- Reproducible data build pipeline for a patient-level clinical NLP corpus.
- Support for both local and Google Drive ingestion.
- Built-in quality checks during parsing (duplicate IDs, expected categories, missing core fields).
- Flexible filtering of metadata rows (for core pool vs use-case splits).
- Dual output format:
  - easy local use (`patients.json` + text files),
  - Hugging Face dataset publication.

## Repository Layout

- `extract_reports.ipynb`: main end-to-end extraction and optional publication notebook.
- `get_stats.ipynb`: statistics and CSV summaries from generated `patients.json`.
- `test_hf_dataset.ipynb`: validation and exploration of the Hugging Face dataset.
- `config/config.yaml`: primary pipeline configuration.
- `config/README_template.md`: template used to generate the Hugging Face dataset card.
- `config/CHANGELOG.md`: dataset changelog injected into generated card.
- `reports_extractor/`: extraction, parsing, normalization, filtering, logging, publication modules.
- `huggingface/parhaf.py`: `datasets` builder class used for dataset creation/push.

## Getting Started

### 1. Prerequisites

- Python `3.10+`
- `pandoc` installed on the system (required by `pypandoc` for DOCX/Markdown conversion)
- Access to input reports (local `.docx` tree or Google Drive + metadata XLSX)

### 2. Create an environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### 3. Install dependencies

No lock file is provided in this repository. Install the packages used by the code and notebooks:

```bash
pip install \
  datasets huggingface_hub \
  pyyaml tqdm pandas numpy \
  openpyxl python-slugify unidecode regex \
  pypandoc google-api-python-client google-auth-oauthlib \
  edsnlp
```

Install Pandoc if missing (for example on Debian/Ubuntu):

```bash
sudo apt-get update && sudo apt-get install -y pandoc
```

### 4. Configure the project

Edit `config/config.yaml`:

- set `input_mode` to `local` or `Google drive`
- set `in_directory`, `out_directory`, and `out_json_file`
- for Google Drive mode, set:
  - `drive_mode.google_credentials_file`
  - `drive_mode.metadata_file`
  - `drive_mode.filter` (for example `filter_core_only` or `filter_entire_training_set`)
- set `hf_dataset` to `True` only if you want to push to Hugging Face

## Usage

### Run extraction (main path)

Open and run `extract_reports.ipynb` from top to bottom.

The notebook:

- loads `config/config.yaml`
- iterates documents via `document_generator(cfg)`
- parses each report with `parse_patient_document(...)`
- writes report text files in specialty subfolders under `out_directory`
- writes metadata JSON (`patients.json`)
- optionally calls `publish_dataset(...)` when `hf_dataset: True`

### Output artifacts

Typical outputs:

- `<out_directory>/patients.json`
- `<out_directory>/<SPECIALTY>/<PATIENT_ID>_<DOCTYPE>.txt`

### Minimal standalone read example

```python
import json
import os

json_path = "./.../patients.json"
with open(json_path, "r", encoding="utf-8") as f:
    root = json.load(f)

patient = root["data"][0]
for doc in patient["documents"]:
    abs_path = os.path.join(os.path.dirname(json_path), doc["path"])
    with open(abs_path, "r", encoding="utf-8") as r:
        text = r.read()
    print(doc["type"], len(text))
```

### Compute corpus statistics

Use `get_stats.ipynb` to generate summary tables and CSV exports from an existing `patients.json`.

### Test Hugging Face loading

Use `test_hf_dataset.ipynb` to inspect dataset loading and patient/document structures.

## Where To Get Help

- Start with the configuration and template files:
  - `config/config.yaml`
  - `config/README_template.md`
  - `config/CHANGELOG.md`
- Review parsing and normalization logic in:
  - `reports_extractor/utils.py`
  - `reports_extractor/normalization.py`
- For operational questions, contact the maintainer listed below.

