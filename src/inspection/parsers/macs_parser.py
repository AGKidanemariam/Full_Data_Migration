"""
MACS document parser.

Combines MACS metadata, header definitions,
and data records into a structured MacsDocument.
"""

from pathlib import Path

from src.inspection.parsers.macs_document import MacsDocument
from src.inspection.parsers.macs_section import MacsSection
from src.inspection.parsers.macs_metadata import MacsMetadataParser
from src.inspection.parsers.macs_header_parser import (

    MacsHeaderParser,
    DEFAULT_SCHEMA_NAME,
)


class MacsParser:
    """
    Parse one complete MACS source file.
    """

    def __init__(self) -> None:
        """
        Initialize shared parser components.
        """

        self.metadata_parser = MacsMetadataParser()

        self.header_parser = MacsHeaderParser()

    def parse(
        self,
        file_path: Path,
        macs_family: str,
    ) -> MacsDocument:
        """
        Parse one MACS file into a MacsDocument.

        Parameters
        ----------
        file_path:
            MACS file to parse.

        macs_family:
            Family identified during inspection.

            Examples:
            FlightState
            Trajectory
            CompMet
            Pilot
            ATC
            Workload

        Returns
        -------
        MacsDocument:
            Structured representation of the MACS file.

        """

        metadata = self.metadata_parser.parse(
            file_path,
        )

        headers = self.header_parser.parse(
            file_path,
        )

        document = MacsDocument(
            file_path=file_path,
            file_name=file_path.name,
            macs_family=macs_family,
            metadata=metadata,
        )

        if not headers:

            document.warnings.append(
                "No MACS header definitions were detected."
            )

            return document

        if DEFAULT_SCHEMA_NAME in headers:

            self._parse_single_schema_file(

                file_path=file_path,
                headers=headers,
                document=document,
            )

        else:

            self._parse_multi_schema_file(
                file_path=file_path,
                headers=headers,
                document=document,
            )

        return document

    def _parse_single_schema_file(
        self,
        file_path: Path,
        headers: dict[str, list[str]],
        document: MacsDocument,
    ) -> None:
        """
        Parse a MACS file containing one table.

        Examples
        --------
        FlightState
        Pilot
        ATC
        """

        header = headers[
            DEFAULT_SCHEMA_NAME
        ]

        section = MacsSection(
            name=document.macs_family,
            header=header,
        )

        data_started = False

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as macs_file:

            for raw_line in macs_file:

                line = raw_line.rstrip(
                    "\r\n",
                )

                stripped_line = line.strip()

                # --------------------------------------------------
                # Ignore everything until END HEADER.
                # --------------------------------------------------

                if not data_started:

                    if stripped_line.upper() == "END HEADER":

                        data_started = True

                    continue

                # --------------------------------------------------
                # Ignore blank lines.
                # --------------------------------------------------

                if not stripped_line:
                    continue

                # --------------------------------------------------
                # Ignore known operational/status messages.
                # --------------------------------------------------

                if self._is_operational_message(
                    stripped_line,
                ):
                    continue

                # --------------------------------------------------
                # Parse the data row.
                # --------------------------------------------------

                fields = line.split("\t")

                # MACS files commonly end data rows with a
                # trailing tab.
                #
                # Example:
                #
                # value1\tvalue2\tvalue3\t
                #
                # split("\t") would produce:
                #
                # ["value1", "value2", "value3", ""]
                #
                # That final empty string is not a real extra
                # column, so remove only that trailing value.
                #
                # Internal empty values are intentionally kept.
                if fields and fields[-1] == "":

                    fields.pop()

                # Some MACS FlightState files may use whitespace
                # instead of literal tabs.
                #
                # Only use whitespace splitting when tab parsing
                # resulted in a single field.
                if len(fields) == 1:

                    fields = stripped_line.split()

                section.rows.append(
                    fields,
                )

        document.sections.append(
            section,
        )

    def _parse_multi_schema_file(
        self,
        file_path: Path,
        headers: dict[str, list[str]],
        document: MacsDocument,
    ) -> None:
        """
        Parse a MACS file containing multiple record types.

        Examples
        --------
        Trajectory
        CompMet
        Workload
        """

        section_lookup: dict[
            str,
            MacsSection,
        ] = {}

        # --------------------------------------------------
        # Create one section for every discovered schema.
        # --------------------------------------------------

        for schema_name, columns in headers.items():

            section = MacsSection(
                name=schema_name,
                header=columns,
            )

            document.sections.append(
                section,
            )

            section_lookup[
                schema_name
            ] = section

        data_started = False

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as macs_file:

            for raw_line in macs_file:

                line = raw_line.rstrip(
                    "\r\n",
                )

                stripped_line = line.strip()

                # --------------------------------------------------
                # Ignore everything until END HEADER.
                # --------------------------------------------------

                if not data_started:

                    if stripped_line.upper() == "END HEADER":

                        data_started = True

                    continue

                # --------------------------------------------------
                # Ignore blank lines.
                # --------------------------------------------------

                if not stripped_line:
                    continue

                # --------------------------------------------------
                # Ignore operational/status messages.
                # --------------------------------------------------

                if self._is_operational_message(
                    stripped_line,
                ):
                    continue

                # --------------------------------------------------
                # Parse tab-delimited record.
                # --------------------------------------------------

                fields = line.split("\t")

                # Remove only the false trailing empty field
                # created by a trailing tab.
                #
                # Do NOT remove internal empty values because
                # their positions are part of the schema.
                if fields and fields[-1] == "":

                    fields.pop()

                if not fields:
                    continue

                record_type = fields[
                    0
                ].strip()

                schema_name = self._resolve_schema_name(
                    record_type=record_type,
                    headers=headers,
                )

                if schema_name is None:

                    document.warnings.append(
                        (
                            "No header mapping found for "
                            f"record type: {record_type}"
                        )
                    )

                    continue

                section = section_lookup[
                    schema_name
                ]

                # The first field is the record type itself.
                # The remaining values belong to the schema.
                section.rows.append(
                    fields[1:],
                )

    def _resolve_schema_name(
        self,
        record_type: str,
        headers: dict[str, list[str]],
    ) -> str | None:
        """
        Map a data record type to its header definition.

        Some MACS files use matching schema/data names.

        Example:
        ATC_DATA -> ATC_DATA

        Trajectory files use MAP definitions for DATA records.

        Examples:
        GLOBAL_DATA -> GLOBAL_MAP
        TRAJPOINT_DATA -> TRAJPOINT_MAP
        """

        # --------------------------------------------------
        # Direct match
        # --------------------------------------------------

        if record_type in headers:

            return record_type

        # --------------------------------------------------
        # Known Trajectory mappings
        # --------------------------------------------------

        trajectory_mapping = {
            "GLOBAL_DATA": "GLOBAL_MAP",
            "TRAJPOINT_DATA": "TRAJPOINT_MAP",
        }

        mapped_name = trajectory_mapping.get(
            record_type,
        )

        if (
            mapped_name is not None
            and mapped_name in headers
        ):

            return mapped_name

        return None

    def _is_operational_message(
        self,
        line: str,
    ) -> bool:
        """
        Return True for known non-data operational messages.

        These lines may appear after END HEADER but should
        not be stored as structured data records.
        """

        normalized = line.lower()

        operational_prefixes = (
            "controller signed-on:",
            "controller sign-in:",
            "criteria ==",
        )

        return normalized.startswith(
            operational_prefixes,
        )