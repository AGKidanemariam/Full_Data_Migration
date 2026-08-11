"""
MACS log reader.

Profiles NASA MACS data files and returns a standardized
DataProfile object.

MACS files may use a .log extension or may be stored
without a file extension.
"""

from pathlib import Path
import csv

from src.common.models.data_profile import DataProfile
from src.inspection.readers.base_reader import BaseReader


SAMPLE_SIZE = 65_536
PREVIEW_LINE_COUNT = 20


class MacsLogReader(BaseReader):
    """
    Reader responsible for profiling MACS data files.
    """

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:
        """
        Return standard extensions associated with MACS logs.
        """

        return (
            ".log",
        )

    def supports(
        self,
        file_path: Path,
    ) -> bool:
        """
        Determine whether a file appears to contain MACS data.

        MACS files may either:

        1. Have a .log extension, or
        2. Be extensionless while following the MACS
           filename naming convention.
        """

        if not file_path.is_file():
            return False

        extension = file_path.suffix.lower()

        if extension == ".log":
            return True

        if extension == "":
            return "_macs_" in file_path.name.lower()

        return False

    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a structural profile describing one MACS file.
        """

        sample = self._read_sample(
            file_path,
        )

        preview_lines = self._read_preview_lines(

            file_path,
        )

        delimiter = self._detect_delimiter(
            sample,
        )

        has_header = self._detect_header(
            sample,
        )

        (
            total_lines,
            non_empty_lines,
        ) = self._count_lines(
            file_path,
        )

        first_fields = self._first_fields(
            sample,
            delimiter,
        )

        macs_family = self._detect_macs_family(
            file_path,
        )

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="MACS_LOG",
            inspection_status="Success",
            inspection_message=(
                "MACS log profile created successfully."
            ),
            encoding="utf-8",
            delimiter=delimiter,
            has_header=has_header,
            total_line_count=total_lines,
            non_empty_line_count=non_empty_lines,
            first_row_fields=first_fields,
            is_empty=non_empty_lines == 0,
            additional_metadata={
                "macs_family": macs_family,
                "extensionless": file_path.suffix == "",
                "first_row_field_count": len(first_fields),
                "preview_lines": preview_lines,
            },
        )

    def _read_sample(
        self,
        file_path: Path,
    ) -> str:
        """
        Read a small text sample for structural analysis.
        """

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            return file.read(
                SAMPLE_SIZE,
            )

    def _read_preview_lines(
        self,
        file_path: Path,
    ) -> list[str]:
        """
        Return the first several non-empty lines.

        This allows us to understand the structure of
        MACS files without loading the entire file.
        """

        preview_lines: list[str] = []

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            for line in file:

                cleaned_line = line.strip()

                if not cleaned_line:
                    continue

                preview_lines.append(
                    cleaned_line,
                )

                if len(preview_lines) >= PREVIEW_LINE_COUNT:
                    break

        return preview_lines

    def _detect_delimiter(
        self,
        sample: str,
    ) -> str | None:
        """
        Attempt generic delimiter detection.

        A blank result is valid when the MACS file contains
        mixed metadata and structured sections.
        """

        if not sample.strip():
            return None

        try:

            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",\t;|",
            )

            return dialect.delimiter

        except csv.Error:

            return None

    def _detect_header(
        self,
        sample: str,
    ) -> bool | None:
        """
        Attempt generic header detection.

        """

        if not sample.strip():
            return None

        try:

            return csv.Sniffer().has_header(
                sample,
            )

        except csv.Error:

            return None

    def _count_lines(
        self,
        file_path: Path,
    ) -> tuple[int, int]:
        """
        Count total and non-empty lines without loading
        the entire file into memory.
        """

        total_lines = 0
        non_empty_lines = 0

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            for line in file:

                total_lines += 1

                if line.strip():
                    non_empty_lines += 1

        return (
            total_lines,
            non_empty_lines,
        )

    def _first_fields(
        self,
        sample: str,
        delimiter: str | None,
    ) -> list[str]:
        """
        Return the fields from the first non-empty row.
        """

        first_line = next(
            (
                line.strip()
                for line in sample.splitlines()
                if line.strip()
            ),
            "",
        )

        if not first_line:
            return []

        if delimiter is None:
            return [
                first_line,
            ]

        return next(
            csv.reader(
                [
                    first_line,
                ],
                delimiter=delimiter,
            ),
            [],
        )

    def _detect_macs_family(
        self,
        file_path: Path,
    ) -> str:
        """
        Identify the likely MACS dataset family from
        the filename.

        This is classification only. Validation will later
        verify the actual file contents against the schema.
        """

        file_name = file_path.name.lower()

        if "_macs_flightstate_" in file_name:
            return "FlightState"

        if "_macs_traj_" in file_name:
            return "Trajectory"

        if "_macs_compmet_" in file_name:
            return "CompMet"

        return "Unknown"