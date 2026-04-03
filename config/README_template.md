---
{{YAML_tags}}
---

# Dataset Card for {{dataset_shortname}}

<div align="center">
<p>
  <a href="https://huggingface.co/spaces/HealthDataHub/PARTAGES" style="display:inline;"><img src="img/PARTAGES BASELINE_RVB.png" alt="Logo" style="height:20px;vertical-align:middle; margin-right:8px; display:inline; margin-bottom:0.2em; margin-top:0.2em;"  title="PARTAGES project"; /></a>
  <a href="https://www.etalab.gouv.fr/wp-content/uploads/2018/11/open-licence.pdf" style="display:inline;" title="Etalab 2.0 license"><img src="img/Logo-licence-ouverte2.svg" style="height:20px; display:inline; margin-bottom:0.2em; margin-top:0.2em;"/></a>
  <a href="https://creativecommons.org/licenses/by/4.0/deed.en" style="display:inline;"><img src="https://mirrors.creativecommons.org/presskit/buttons/88x31/png/by.png" style="height:20px; display:inline; margin-bottom:0.2em; margin-top:0.2em;" title="CC BY 4.0 license"/></a>
  <a href="{{paper_url}}"><img src="https://img.shields.io/badge/Paper-red?logo=arxiv&logoColor=white" style="height:20px; display:inline; margin-bottom:0.2em; margin-top:0.2em;" title="Paper"/></a>
</p>
</div>

{{TABLE_OF_CONTENTS}}

## Reporting Issues & Contributing

If you encounter any errors or inconsistencies in this dataset, please report them in the discussion section of the "Community" tab on Hugging Face.

For more substantial contributions or collaboration opportunities, feel free to contact us directly.


## Dataset Description

{{dataset_split_description}}

**Paper:** {{paper_url}}


### Dataset Summary

{{dataset_shortname}} is an open French corpus of human-authored clinical reports of fictional patients. It was created to support the development and evaluation of clinical NLP systems under strict health-data protection constraints. Each patient is each documented with structured clinical information (diagnosis, procedures, care pathway, discharge data). 

Each patient record was written by a senior medical resident and reviewed by another senior medical resident, from the same specialty. You can consult the [guidelines provided to the writers and reviewers (in French)](doc/PARTAGES_Guide_methodologique_de_redaction_et_de_relecture_des_CR_fictifs.pdf).


#### Data statistics

{{corpus_statistics}}

Note: In case you wonder why CU 1 (Pseudonymisation) is not listed below: The patients for this use case have been sampled from the general distribution, that's why they don't appear here. To know which documents are part of this use case, consult the specific dataset PARCOMED.

#### Data Origin

The clinical reports were authored by senior medical residents specifically for this corpus.

The source data for building clinical scenarios comes from National Hospital claims data available in the SNDS national French database. To comply with privacy regulations regarding the use of SNDS data, scenarios are built by sampling on the observed distributions. The diagnosis distribution aims at reducing the over-representation of very common conditions and including less frequent situations.

The writers were provided with a scenario made of:
- A primary diagnosis
- A patient age
- An admission mode (when relevant)
- A discharge mode (when relevant)
- A type of care (when relevant)

A list of common secondary diagnoses for the specified primary diagnoses was also provided for information.

A standardized clinical report template was also provided to the writers. It defined a generic structure designed to reflect the expected logic of clinical documentation. It includes the core sections of a medical report (such as patient history, clinical findings, assessment, and care plan) while remaining flexible through adaptable templates based on the report type, medical specialty, and identified use cases.

#### Intended usages

This dataset can be used to support a variety of applications, including:

- Sharing clinical notes and annotations
- Pooling efforts within the clinical NLP community
- Benchmarking French medical LLMs
- Enabling reproducible clinical NLP research
- Supporting medical teaching and education
- Promoting work on PARTAGES’s 7 use cases
- Enabling privacy-safe data augmentation


#### Excluded usages

The dataset is not intended to be used for

- Clinical decision-making or patient care (no diagnostic, prognostic, or therapeutic use)
- Clinical validation or performance claims (models trained on this data are not clinically validated)
- Generalization to unseen hospitals, regions, or practices
- Epidemiological or population-level inference (≠ real-world prevalence or distributions)
- Assessing real-world safety or clinical risk (rare adverse events, edge cases)
- Replacing real clinical data for deployment (research-only)
- Stress-testing models on realistic clinical language (no time pressure, workload, interruptions)

This dataset is limited to hospital-based clinical documentation and focuses on selected document types that are central to the patient record but not representative of the full range of medical documentation. It excludes several important categories, such as imaging reports, prescriptions, referral letters, and procedural or operative reports, and therefore does not capture the full diversity of clinical documentation.


### Languages

- fr_FR


## Dataset Structure

We distribute both a Hugging Face dataset and a standalone version of the corpus. The standalone JSON files constitute the canonical version of the corpus. The Hugging Face dataset (Parquet/Arrow) is a derived representation generated automatically from the JSON files.

Both formats therefore contain identical information and differ only in storage layout.


### Standalone corpus (out of Hugging Face)

The standalone dataset consists of a single JSON file containing structured metadata about fictitious patients and the clinical documents associated with them. Each entry in the **data** array corresponds to one patient record and includes patient-level metadata, contextual information about the care scenario, and a list of associated documents.

The documents themselves are **not embedded** in the JSON file. Instead, each document is referenced via a relative file path pointing to an external text file. These text files are stored separately and organized by medical specialty, with one directory per specialty. Each document file contains raw, unannotated plain text in French, with no markup, labels, or structural tags applied.

The JSON file, therefore, serves as the index and metadata layer for the corpus, while the directory structure contains the raw textual content. The linkage between metadata and text relies exclusively on the relative paths specified in the `documents[].path` fields.


```python
import json
import os
with open(json_path, "r") as f:
    data = json.load(f)
    
patients = data["data"]
patient = patients[0]       # First patient
patient_id = patient["id"]
specialty = patient["specialty"]
scenario = patient["suggested_scenario"]
patient_fake_name = scenario["name"]
primary_diagnosis = scenario["primary_diagnosis"]
patient_reports = patient["documents"]
...

# Each patient can have one, two or three reports
for report in patient_reports:
    type = report["type"]
    path = report["path"]
    # The content of the report is not in the JSON file
    # but in distinct text files
    abs_path = os.path.join(os.path.dirname(json_path), path)
    with open(abs_path, "r") as f:
        text = f.read()
    print(type, text)
    ...
```

### Hugging Face dataset

The Hugging Face dataset and the standalone JSON file contain the same information but use different data representations.
First, in the Hugging Face dataset (parquet format), the textual content of the document is embedded in the dictionary.
Second, the JSON standalone representation follows a conventional nested structure (a list of objects, each containing a list of `{type, text}` dictionaries), as described below in the description of data instances.


In contrast, the Hugging Face version is stored using a columnar format optimized for efficient loading and machine learning.
As a consequence, sequences of dictionaries are represented as a dictionary of lists (one list per field) rather than a list of dictionaries.
This structural change does not alter the data content, only its storage layout. 

```python
from datasets import load_dataset

ds = load_dataset("{{dataset_name}}")
patient = ds["train"][0]       # First patient
patient_id = patient["id"]
specialty = patient["specialty"]
scenario = patient["suggested_scenario"]
patient_fake_name = scenario["name"]
primary_diagnosis = scenario["primary_diagnosis"]
patient_reports = patient["documents"]
...
# In Hugging Face dataset, sequences of dictionaries are represented 
# as a dictionary of lists (one list per field) rather than a list of dictionaries.
types = patient_reports["type"]
texts = patient_reports["text"]
for type, text in zip(types, texts):
    print(type, text)
    ...
```


### Data Instances

One dataset instance corresponds to **one patient** and contains all associated documents and metadata.

Each example includes:

- `id`: patient identifier
- `local_id`
- `specialty`
- `author`
- `reviewer`
- `pool`
- `suggested_scenario`: structured clinical metadata
- `documents`: list of clinical reports with full text
- `structured_abstract`: optional structured summary

The dataset preserves a hierarchical patient-level organization. Note that 
this corresponds to the standalone dataset; As mentioned above, the HF dataset is stored using a columnar format.

```
patient
 ├─ id: string
 ├─ local_id: string
 ├─ specialty: string
 ├─ author: string
 ├─ reviewer: string
 ├─ pool: string
 ├─ suggested_scenario:
 │   ├─ name: string
 │   ├─ age:
 │   │   ├─ value: integer
 │   │   └─ unit: string
 │   ├─ sex: string
 │   ├─ admission_mode: string (optional)
 │   ├─ discharge_mode: string (optional)
 │   ├─ primary_procedure: {code, description} (optional)
 │   ├─ primary_diagnosis: {code, description}
 │   └─ type_of_care: string (optional)
 ├─ documents: [document]
 │   └─ document
 │       ├─ type: string
 │       ├─ header: string
 │       ├─ path: string
 │       └─ word_count: integer
 └─ structured_abstract (optional)
     ├─ primary_diagnosis: [{code?, description}]
     ├─ primary_procedure: [{code, description}]
     ├─ admission_mode: string
     ├─ discharge_mode: string
     └─ length_of_stay: {value, unit}
```


### Data Fields

Field names use dot notation to describe nested objects.

#### ```data[]```(one patient)

| Path                  | Type   | Description                                                                     |
| --------------------- | ------ | ------------------------------------------------------------------------------- |
| `id`                  | string | Global unique patient identifier                                                |
| `local_id`            | string | Local identifier within the specialty                                           |
| `specialty`           | string | Medical specialty                                                               |
| `author`              | string | Author trigram                                                                  |
| `reviewer`            | string | Reviewer trigram                                                                |
| `pool`                | string | Dataset partition. Some patients belong to specific use cases (CU1–CU6)         |
| `suggested_scenario`  | dict   | Scenario provided to the report writer                                          |
| `documents[]`         | array  | List of reports for this patient                                                |
| `structured_abstract` | dict   | Optional uncurated abstract written by the author. May not match report content |


#### `suggested_scenario`

| Path                            | Type    | Description            |
| ------------------------------- | ------- | ---------------------- |
| `name`                          | string  | Fictional patient name |
| `age.value`                     | integer | Age value              |
| `age.unit`                      | string  | Age unit               |
| `sex`                           | string  | Patient sex            |
| `admission_mode`                | string  | Admission source       |
| `discharge_mode`                | string  | Discharge destination  |
| `primary_procedure.code`        | string  | CCAM code              |
| `primary_procedure.description` | string  | Procedure label        |
| `primary_diagnosis.code`        | string  | ICD-10 code            |
| `primary_diagnosis.description` | string  | Diagnosis label        |
| `type_of_care`                  | string  | Care description       |


#### `documents[]`(patients reports, 1-3 per patient)

| Path         | Type    | Description                   |
| ------------ | ------- | ----------------------------- |
| `type`       | string  | Document type                 |
| `header`     | string  | Document title                |
| `word_count` | integer | Number of words in the report |
| `path`       | string  | Relative path to raw text     |

### Controlled Vocabularies

The following fields use closed sets of values and should be treated as categorical variables rather than free text.

#### `specialty`

```
ANATOMOPATHOLOGIE
CANCERO ADULTE
CARDIOLOGIE
CHIR ORTHO ET TRAUMATO
CHIR.CARDIO-VASC.
CHIRURGIE VISCERALE
GYNECOLOGIE
HEMATOLOGIE CLINIQUE
HEPATO-GASTRO-ENTERO
MALADIES INFECTIEUSES
MEDECINE GERIATRIQUE
MEDECINE INTER-SPECIALITES
MEDECINE INTERNE
MEDECINE PEDIATRIQUE
NEPHROLOGIE
NEUROLOGIE
OBSTETRIQUE
PNEUMOLOGIE
REANIMATION
UROLOGIE
```

#### `pool`

```
'CU 1 - Pseudonymisation'
'CU 2 - ICD-10 coding' 
'CU 5a - Oncology (biomarkers)', 
'CU 5b - Oncology (response to treatment)', 
'CU 6 - Infectiology', 
'General'
```


#### `age.unit`

```
'ans', 
'mois'
```

#### `sex`

```
'F',
'M'
```


#### `admission_mode`

```
'admission non programmée suite à un contact avec le médecin traitant dans les 48h',
'admission non programmée suite à un contact avec un médecin suivant le patient en consultation (médecin traitant par exemple) dans les 48h',
'admission par les urgences',
'domicile',
'domicile (à modifier pour entrée par les urgences)',
'domicile sans passer par le service des urgences',
'domicile- service de gastro-entérologie',
'entrée par les urgences',
"entrée par un autre service d'hospitalisation",
"transfert d'un autre hôpital",
'transfert depuis un autre service',
'transfert par le service des urgences',
'urgences'
None
```

#### `discharge_mode`

```
'admission en smr',
'domicile',
'décès',
'retour au soins de suite et réadaptation',
'retour à domicile',
'retour à domicile -> hématologie stérile',
'retour à domicile ; transfert gastrologie',
'retour à domicile > changer pour transfert en chirurgie digestive',
'retour à domicile → hospitalisation',
'sortie en soins de suite',
'ssr neurologique',
'transfert',
'transfert dans un autre hôpital',
'transfert dans un autre service',
'transfert en gastro-entérologie',
'transfert en gynécologie',
'transfert en psychiatrie',
'transfert en soins de suite et réadaptation',
'transfert en soins de suite et rééducation'
None
```

#### Document's `type`

```
'ACCOUCHEMENT',  # Birth 
'ANAPATH',       # Pathology report
'CRC',           # CR consultation
'CRH',           # CR hospitalisation
'CRO',           # CR opération
'MATERNITE',     # Maternity
'URGENCES'       # ER
```

### Data Splits

{{dataset_split_description}}


## Dataset Creation

PARTAGES releases an open corpus of human-authored medical reports in French that will enable players from industry and academia to address specific use cases based on general medical generative LLMs.

This was made possible by:

- A partnership with over 17 associations and unions of medical residents, in multiple medical and surgical specialties : 120 medical residents were recruited as writers;
- The creation of guidelines to choose clinical cases based on Data from the National Health Data System (SNDS) as support scenarios to author medical reports;
- The authoring by medical residents of synthetic medical reports;
- The creation of an open-source corpus in French to train and evaluate language models on specific use cases.


{{CHANGELOG}}


## Additional Information

### Licensing Information

This dataset is released under licenses:

- CC BY 4.0
- Etalab 2.0

### Citation Information

[More Information Needed]



