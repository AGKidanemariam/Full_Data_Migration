"""
Shared data profile model.

Every reader in the inspection stage returns
a DataProfile object describing one source file.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DataProfile:
    """
    Standard profile describing one discovered file.

    Every reader populates the fields that apply to
    its specific file format.
    """

    # --------------------------------------------------
    # General file information
    # --------------------------------------------------

    file_path: Path

    file_name: str

    extension: str

    file_size_bytes: int

    profile_type: str

    inspection_status: str

    inspection_message: str = ""

    # --------------------------------------------------
    # Generic structural information
    # --------------------------------------------------

    encoding: str | None = None

    delimiter: str | None = None

    has_header: bool | None = None

    row_count: int | None = None

    column_count: int | None = None

    column_names: list[str] = field(
        default_factory=list,
    )

    is_empty: bool | None = None

    # --------------------------------------------------
    # JSON specific
    # --------------------------------------------------

    root_type: str | None = None

    top_level_keys: list[str] = field(
        default_factory=list,
    )

    # --------------------------------------------------
    # XML specific
    # --------------------------------------------------

    root_element: str | None = None

    namespace_count: int | None = None

    # --------------------------------------------------
    # Text / Log specific
    # --------------------------------------------------

    total_line_count: int | None = None

    non_empty_line_count: int | None = None

    first_row_fields: list[str] = field(
        default_factory=list,
    )

    # --------------------------------------------------
    # Future expansion
    # --------------------------------------------------

    additional_metadata: dict[str, Any] = field(
        default_factory=dict,
    )