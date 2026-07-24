"""
Reader registry.

Maintains all available profiling readers and
selects the correct reader for a given file.
"""

from pathlib import Path

from src.inspection.readers.base_reader import BaseReader
from src.inspection.readers.csv_reader import CsvReader
from src.inspection.readers.txt_reader import TxtReader
from src.inspection.readers.json_reader import JsonReader
from src.inspection.readers.xml_reader import XmlReader
from src.inspection.readers.macs_log_reader import MacsLogReader


class ReaderRegistry:
    """
    Registry of all available readers.
    """

    def __init__(self) -> None:

        self._readers: list[BaseReader] = [
            CsvReader(),
            TxtReader(),
            JsonReader(),
            XmlReader(),
            MacsLogReader(),
        ]

    def get_reader(
        self,
        file_path: Path,
    ) -> BaseReader | None:
        """
        Return the first reader that supports the file.
        """

        for reader in self._readers:

            if reader.supports(file_path):

                return reader

        return None

    @property
    def readers(
        self,
    ) -> list[BaseReader]:
        """
        Return all registered readers.
        """

        return self._readers