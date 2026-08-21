"""
MACS document model.

Represents one parsed MACS source file,
including file-level metadata and one or more
structured data sections.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.inspection.parsers.macs_section import ( MacsSection,)


@dataclass(slots=True)
class MacsDocument:
    """
    Structured representation of one MACS file.
    """

    file_path: Path

    file_name: str

    macs_family: str

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    sections: list[MacsSection] = field(
        default_factory=list,
    )

    warnings: list[str] = field(
        default_factory=list,
    )

    @property
    def section_count(self) -> int:
        """
        Number of structured sections in the document.
        """

        return len(
            self.sections,
        )

    def get_section(
        self,
        section_name: str,
    ) -> MacsSection | None:
        """
        Return a section by name.

        Matching is case-insensitive.
        """

        requested_name = section_name.lower()

        for section in self.sections:

            if section.name.lower() == requested_name:
                return section

        return None