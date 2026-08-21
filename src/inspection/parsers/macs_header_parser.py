"""
MACS header parser.

Extracts tab-delimited schema definitions from
the header portion of a MACS log file.

Supports both:

1. Single-schema MACS files such as FlightState.
2. Multi-schema MACS files such as Trajectory and CompMet.
"""

from pathlib import Path


DEFAULT_SCHEMA_NAME = "DEFAULT"


class MacsHeaderParser:
    """
    Parse structured MACS header definitions.
    """

    def parse(
        self,
        file_path: Path,
    ) -> dict[str, list[str]]:
        """
        Parse all schema definitions from one MACS file.

        Returns
        -------
        dict[str, list[str]]

        Single-schema example:

        {
            "DEFAULT": [
                "UTC_TIME",
                "WEIGHT",
                "FUEL_RATE",
                ...
            ]
        }

        Multi-schema example:

        {
            "GLOBAL_MAP": [
                "EVENT_TYPE",
                "UTC_TIME",
                ...
            ],

            "TRAJPOINT_MAP": [
                "EVENT_TYPE",
                "UTC_TIME",
                ...
            ]
        }
        """

        header_lines = self._read_header_lines(
            file_path,
        )

        if not header_lines:
            return {}

        # --------------------------------------------------
        # Single structured header
        # --------------------------------------------------
        #
        # Example:
        #
        # UTC_TIME    WEIGHT    FUEL_RATE ...
        #
        # In this structure, every field is a column name.
        # There is no record-type identifier.
        # --------------------------------------------------

        if len(header_lines) == 1:

            return {
                DEFAULT_SCHEMA_NAME: header_lines[0],
            }

        # --------------------------------------------------
        # Multiple structured headers
        # --------------------------------------------------
        #
        # Example:
        #
        # GLOBAL_MAP       EVENT_TYPE ...
        # TRAJPOINT_MAP    EVENT_TYPE ...
        #
        # The first field identifies the schema.
        # --------------------------------------------------

        headers: dict[str, list[str]] = {}

        for fields in header_lines:

            if not fields:
                continue

            schema_name = fields[0]

            columns = fields[1:]

            headers[
                schema_name
            ] = columns

        return headers

    def _read_header_lines(
        self,
        file_path: Path,
    ) -> list[list[str]]:
        """
        Read every tab-delimited schema line appearing
        before the END HEADER marker.
        """

        header_lines: list[list[str]] = []

        structured_header_started = False

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

                if not stripped_line:
                    continue

                # ------------------------------------------
                # End of header area
                # ------------------------------------------

                if stripped_line.upper() == "END HEADER":
                    break

                # ------------------------------------------
                # Metadata lines do not contain tabs.
                # ------------------------------------------

                if "\t" not in line:

                    if not structured_header_started:
                        continue

                    continue

                structured_header_started = True

                fields = [
                    field.strip()
                    for field in line.split("\t")
                ]

                # Remove empty fields only from the end.
                #
                # We must preserve internal empty values
                # because position matters in a schema.
                while fields and not fields[-1]:
                    fields.pop()

                if fields:
                    header_lines.append(
                        fields,
                    )

        return header_lines
