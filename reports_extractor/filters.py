from openpyxl.cell.cell import Cell
from typing import List
import logging

logger = logging.getLogger("filters")

# Functions to filter rows for any purposes
# The filters should be used in the pipeline as needed
# The yaml config can be used to choose the filter to apply


def filter_raw_to_annotate(row: List[Cell]) -> bool:
    """
    Filter rows to keep only those that need to be annotated.
    A row needs annotation if the "Task" column is set to "A annoter".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    bool
        True if the row needs annotation, False otherwise.
    """
    task_cell = row[8]  # Assuming the "task" column is the 9th column (index 8)
    return task_cell.value == "A annoter"


def filter_reviewed_raw(row: List[Cell]) -> bool:
    """
    Filter rows to keep only those that have been reviewed.
    A row is considered reviewed if the "Status" column is set to "Relu".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    bool
        True if the row matches the criteria, False otherwise.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    return status_cell.value == "Relu"


def filter_reviewed_CU6(row: List[Cell]) -> bool:
    """
    Filter rows to keep only those that have been reviewed, CU6 only.
    A row is considered reviewed if the "Status" column is set to "Relu".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    bool
        True if the row matches the criteria, False otherwise.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    cu_cell = row[28]
    return status_cell.value == "Relu" and cu_cell.value == "CU 6"


def filter_core_only(row: List[Cell]) -> bool:
    """
    Filter rows to keep only those that have been reviewed, "core only" ("pool général")
    All patients for specific use cases are discarded.
    A row is considered reviewed if the "Status" column is set to "Relu".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    bool
        True if the row matches the criteria, False otherwise.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    cu_cell = row[28]
    return status_cell.value == "Relu" and cu_cell.value == "Pool Général"


def filter_entire_training_set(row: List[Cell]) -> bool:
    """
    Filter rows to keep only those that have been reviewed, for the entire training set.
    The training set includes both "core only" ("pool général") and training patients from use cases.
    A row is considered reviewed if the "Status" column is set to "Relu".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    bool
        True if the row matches the criteria, False otherwise.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    cu_cell = row[28]  # Pool: "pool général" or "CUx"
    split = row[29]  # TRAIN, TEST or empty for the core set
    split_value = split.value
    if status_cell.value != "Relu":
        return False
    if cu_cell.value == "Pool Général":
        if split_value != "" and split_value is not None:
            raise ValueError(
                f"Unexpected split value for Pool Général: {split_value} for cell {row[0].value}"
            )
        return True
    if str(cu_cell.value) in ["CU 1", "CU 2", "CU 5a", "CU 5b", "CU 6"]:
        if split_value == "TRAIN":
            return True
        elif split_value == "TEST":
            return False
        else:
            raise ValueError(
                f"Unexpected split value: {split_value} for cell {row[0].value}"
            )
    else:
        raise ValueError(
            f"Unexpected CU value: {cu_cell.value} for cell {row[0].value}"
        )
    return status_cell.value == "Relu" and (cu_cell.value == "Pool Général")
