import json
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Any

import datasets


class ParhafConfig(datasets.BuilderConfig):
    """BuilderConfig for MyDataset."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class Parhaf(datasets.GeneratorBasedBuilder):
    """Clinical patient-level dataset with hierarchical structure."""

    BUILDER_CONFIGS = [
        ParhafConfig(
            name="default",
            version=datasets.Version("0.0.0"),  # placeholder version
            description="PARHAF",
        )
    ]

    DEFAULT_CONFIG_NAME = "default"

    # def __init__(self, json_path: str, hf_dataset_directory: str, *args, **kwargs):
    def __init__(self, json_path: str, config: Dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._json_path = json_path
        version = config["dataset_version"]
        description = config["dataset_description"]
        self.config.version = datasets.Version(version)
        self.config.description = description

        # self._hf_dataset_directory = hf_dataset_directory

    def version(self) -> datasets.Version:
        """Return the dataset version."""
        return self.config.version  # type: ignore

    def _info(self) -> datasets.DatasetInfo:
        """Define dataset features."""
        return datasets.DatasetInfo(
            description=(
                self.config.description if self.config.description else "PARHAF"
            ),
            version=self.config.version,
            features=datasets.Features(
                {
                    "id": datasets.Value("string"),
                    "local_id": datasets.Value("string"),
                    "specialty": datasets.Value("string"),
                    "author": datasets.Value("string"),
                    "reviewer": datasets.Value("string"),
                    "pool": datasets.Value("string"),
                    "suggested_scenario": {
                        "name": datasets.Value("string"),
                        "age": {
                            "value": datasets.Value("int32"),
                            "unit": datasets.Value("string"),
                        },
                        "sex": datasets.Value("string"),
                        "admission_mode": datasets.Value("string"),
                        "discharge_mode": datasets.Value("string"),
                        "primary_procedure": {
                            "code": datasets.Value("string"),
                            "description": datasets.Value("string"),
                        },
                        "primary_diagnosis": datasets.Sequence(
                            {
                                "code": datasets.Value("string"),
                                "description": datasets.Value("string"),
                            }
                        ),
                        "type_of_care": datasets.Value("string"),
                    },
                    "documents": datasets.Sequence(
                        {
                            "type": datasets.Value("string"),
                            "header": datasets.Value("string"),
                            "text": datasets.Value("string"),
                            "word_count": datasets.Value("int32"),
                        }
                    ),
                    "structured_abstract": {
                        "primary_diagnosis": datasets.Sequence(
                            {
                                "code": datasets.Value("string"),
                                "description": datasets.Value("string"),
                            }
                        ),
                        "primary_procedure": datasets.Sequence(
                            {
                                "code": datasets.Value("string"),
                                "description": datasets.Value("string"),
                            }
                        ),
                        "admission_mode": datasets.Value("string"),
                        "discharge_mode": datasets.Value("string"),
                        "length_of_stay": {
                            "value": datasets.Value("int32"),
                            "unit": datasets.Value("string"),
                        },
                    },
                }
            ),
            supervised_keys=None,
        )

    def _split_generators(self, dl_manager: datasets.DownloadManager):  # type: ignore
        """Define dataset splits."""
        # data_dir = Path(self.config.data_dir or "data")
        # json_path = dl_manager.download_and_extract(data_dir / "patients.json")
        # print(f"Downloaded JSON file: {json_path}")

        return [
            datasets.SplitGenerator(
                name=datasets.Split.TRAIN,  # type: ignore
                # gen_kwargs={
                #     "json_path": self._json_path,
                # },
            )
        ]

    def _generate_examples(  # type: ignore
        self,
    ) -> Iterator[Tuple[int, Dict[str, Any]]]:
        """Yield one example per patient."""
        json_path = Path(self._json_path)
        data_dir = json_path.parent

        with open(json_path, "r", encoding="utf-8") as f:
            root = json.load(f)

        for idx, patient in enumerate(root["data"]):
            documents: List[dict] = []
            for doc in patient["documents"]:
                internal_path = doc["path"]  # ex: patient_001/report.txt
                with open(data_dir / internal_path, "r", encoding="utf-8") as f:
                    text = f.read()

                # text_path = root_dir / doc["path"]
                # text = text_path.read_text(encoding="utf-8")
                documents.append(
                    {
                        "type": doc["type"],
                        "header": doc["header"],
                        "text": text,
                        "word_count": doc["word_count"],
                    }
                )
            example = dict(patient)
            print("documents", documents)
            example["documents"] = documents
            yield idx, example
