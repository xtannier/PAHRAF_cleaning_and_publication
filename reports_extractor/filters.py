import enum

from openpyxl.cell.cell import Cell
from typing import List, Tuple
import logging

logger = logging.getLogger("filters")

# Functions to filter rows for any purposes
# The filters should be used in the pipeline as needed
# The yaml config can be used to choose the filter to apply


# Constants to represent the different filtering outcomes
class FilterOutcome(enum.Enum):
    REJECT = 0  # The row is rejected and should not be included in the dataset
    ACCEPT_STRICT = 1  # The row is accepted and should be included in the dataset, strict mode (i.e names of the author, reviewer, etc. must be present)
    ACCEPT_LAX = 2  # The row is accepted and should be included in the dataset, lax mode (i.e names of the author, reviewer, etc. are not required)


def filter_raw_to_annotate(row: List[Cell]) -> FilterOutcome:
    """
    Filter rows to keep only those that need to be annotated.
    A row needs annotation if the "Task" column is set to "A annoter".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    FilterOutcome
        The outcome of the filter.
    """
    task_cell = row[8]  # Assuming the "task" column is the 9th column (index 8)
    if task_cell.value == "A annoter":
        return FilterOutcome.ACCEPT_STRICT
    else:
        return FilterOutcome.REJECT


def filter_reviewed_raw(row: List[Cell]) -> FilterOutcome:
    """
    Filter rows to keep only those that have been reviewed.
    A row is considered reviewed if the "Status" column is set to "Relu".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    FilterOutcome
        The outcome of the filter.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    if status_cell.value == "Relu":
        return FilterOutcome.ACCEPT_STRICT
    else:
        return FilterOutcome.REJECT


def filter_reviewed_CU6(row: List[Cell]) -> FilterOutcome:
    """
    Filter rows to keep only those that have been reviewed, CU6 only.
    A row is considered reviewed if the "Status" column is set to "Relu".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    FilterOutcome
        The outcome of the filter.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    cu_cell = row[28]
    if status_cell.value == "Relu" and cu_cell.value == "CU 6":
        return FilterOutcome.ACCEPT_STRICT
    else:
        return FilterOutcome.REJECT


def filter_core_only(row: List[Cell]) -> FilterOutcome:
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
    FilterOutcome
        The outcome of the filter.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    cu_cell = row[28]
    if status_cell.value == "Relu" and cu_cell.value == "Pool Général":
        return FilterOutcome.ACCEPT_STRICT
    else:
        return FilterOutcome.REJECT


def filter_entire_training_set(row: List[Cell]) -> FilterOutcome:
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
    FilterOutcome
        The outcome of the filter.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    cu_cell = row[28]  # Pool: "pool général" or "CUx"
    split = row[29]  # TRAIN, TEST or empty for the core set
    split_value = split.value
    if status_cell.value != "Relu":
        return FilterOutcome.REJECT
    if cu_cell.value == "Pool Général":
        if split_value != "" and split_value is not None:
            raise ValueError(
                f"Unexpected split value for Pool Général: {split_value} for cell {row[0].value}"
            )
        return FilterOutcome.ACCEPT_STRICT
    if str(cu_cell.value) in ["CU 1", "CU 2", "CU 5a", "CU 5b", "CU 6"]:
        if split_value == "TRAIN":
            return FilterOutcome.ACCEPT_STRICT
        elif split_value == "TEST":
            return FilterOutcome.REJECT
        else:
            raise ValueError(
                f"Unexpected split value: {split_value} for cell {row[0].value}"
            )
    else:
        raise ValueError(
            f"Unexpected CU value: {cu_cell.value} for cell {row[0].value}"
        )


def filter_rejected_documents(row: List[Cell]) -> FilterOutcome:
    """
    Filter rows to keep only those that have been rejected.
    A row is considered rejected if the "Status" column is set to "Rejeté".

    Parameters
    ----------
    row : List[Cell]
        A row from the Excel sheet.

    Returns
    -------
    FilterOutcome
        The outcome of the filter.
    """
    status_cell = row[13]  # Assuming the "Status" column is the 14th column (index 12)
    review_status_cell = row[
        20
    ]  # Assuming the "Review status" column is the 21th column (index 20)
    return (
        FilterOutcome.ACCEPT_LAX
        if status_cell.value == "Eliminé" and review_status_cell.value == "Terminé"
        else FilterOutcome.REJECT
    )
