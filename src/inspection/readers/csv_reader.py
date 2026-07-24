"""
CSV reader.

Profiles CSV files and returns a DataProfile.
"""

from pathlib import Path

import pandas as pd

from src.common.models.data_profile import DataProfile
from src.inspection.readers.base_reader import BaseReader


class CsvReader(BaseReader):
    """
    Reader responsible for profiling CSV files.
    """

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:

        return (
            ".csv",
        )

    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a profile describing one CSV file.
        """

        dataframe = pd.read_csv(
            file_path,
            low_memory=False,
        )

        column_names = (
            dataframe.columns
            .astype(str)
            .tolist()
        )

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="CSV",
            inspection_status="Success",
            inspection_message="CSV profile created successfully.",
            encoding="utf-8",
            delimiter=",",
            has_header=True,
            row_count=len(dataframe),
            column_count=len(column_names),
            column_names=column_names,
            is_empty=dataframe.empty,
        )
