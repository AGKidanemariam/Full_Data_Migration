"""
JSON reader.

Profiles JSON files and returns a DataProfile.
"""

from pathlib import Path
import json

from src.common.models.data_profile import DataProfile
from src.inspection.readers.base_reader import BaseReader


class JsonReader(BaseReader):
    """
    Reader responsible for profiling JSON files.
    """

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:

        return (
            ".json",
            ".jsonl",
        )

    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a profile describing one JSON file.
        """

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as json_file:

            data = json.load(json_file)

        root_type = type(data).__name__

        top_level_keys: list[str] = []

        row_count = None

        if isinstance(data, dict):

            top_level_keys = list(data.keys())

        elif isinstance(data, list):

            row_count = len(data)

            if data and isinstance(data[0], dict):

                top_level_keys = list(
                    data[0].keys()
                )

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="JSON",
            inspection_status="Success",
            inspection_message="JSON profile created successfully.",
            encoding="utf-8",
            row_count=row_count,
            root_type=root_type,
            top_level_keys=top_level_keys,
            is_empty=(
                len(data) == 0
                if isinstance(data, (list, dict))
                else False
            ),
        )