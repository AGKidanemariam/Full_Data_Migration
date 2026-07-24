"""
TXT reader.

Profiles plain text files and returns a DataProfile.
"""

from pathlib import Path

from src.common.models.data_profile import DataProfile
from src.inspection.readers.base_reader import BaseReader


class TxtReader(BaseReader):
    """
    Reader responsible for profiling plain text files.
    """

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:

        return (
            ".txt",
        )

    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a profile describing one text file.
        """

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as text_file:

            lines = text_file.readlines()

        non_empty_lines = [
            line
            for line in lines
            if line.strip()
        ]

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="TXT",
            inspection_status="Success",
            inspection_message="TXT profile created successfully.",
            encoding="utf-8",
            total_line_count=len(lines),
            non_empty_line_count=len(non_empty_lines),
            is_empty=len(non_empty_lines) == 0,
        )