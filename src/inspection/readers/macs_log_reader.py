"""
MACS log reader.

Profiles MACS log files and returns a DataProfile.
"""

from pathlib import Path
import csv

from src.common.models.data_profile import DataProfile
from src.inspection.readers.base_reader import BaseReader


SAMPLE_SIZE = 65536


class MacsLogReader(BaseReader):
    """
    Reader responsible for profiling MACS log files.
    """

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:

        return (
            ".log",
        )

    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a profile describing one MACS log file.
        """

        sample = self._read_sample(file_path)

        delimiter = self._detect_delimiter(sample)

        has_header = self._detect_header(sample)

        (
            total_lines,
            non_empty_lines,
        ) = self._count_lines(file_path)

        first_fields = self._first_fields(
            sample,
            delimiter,
        )

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="MACS_LOG",
            inspection_status="Success",
            inspection_message="MACS log profile created successfully.",
            encoding="utf-8",
            delimiter=delimiter,
            has_header=has_header,
            total_line_count=total_lines,
            non_empty_line_count=non_empty_lines,
            first_row_fields=first_fields,
            is_empty=non_empty_lines == 0,
        )

    def _read_sample(
        self,
        file_path: Path,
    ) -> str:

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            return file.read(SAMPLE_SIZE)

    def _detect_delimiter(
        self,
        sample: str,
    ) -> str | None:

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

        if not sample.strip():
            return None

        try:

            return csv.Sniffer().has_header(sample)

        except csv.Error:

            return None

    def _count_lines(
        self,
        file_path: Path,
    ) -> tuple[int, int]:

        total = 0

        non_empty = 0

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            for line in file:

                total += 1

                if line.strip():

                    non_empty += 1

        return (
            total,
            non_empty,
        )

    def _first_fields(
        self,
        sample: str,
        delimiter: str | None,
    ) -> list[str]:

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