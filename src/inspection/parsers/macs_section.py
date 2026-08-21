"""
MACS section model.

Represents one structured tabular section
inside a MACS document.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MacsSection:
    """
    One logical table contained inside a MACS file.

    Examples
    --------
    FlightState files may contain one primary section.

    Trajectory files may contain sections such as:

    GLOBAL_DATA
    TRAJPOINT_DATA
    """

    name: str

    header: list[str] = field(
        default_factory=list,
    )

    rows: list[list[str]] = field(
        default_factory=list,
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    @property
    def column_count(self) -> int:
        """
        Number of columns defined by the section header.
        """

        return len(
            self.header,
        )

    @property
    def row_count(self) -> int:
        """
        Number of parsed data rows.
        """

        return len(
            self.rows,
        )
