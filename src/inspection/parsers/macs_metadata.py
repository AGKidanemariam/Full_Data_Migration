"""
MACS metadata parser.

Extracts common file-level metadata from the beginning
of a MACS source file.

The metadata section appears before the structured
tab-delimited header definitions.
"""

from pathlib import Path
from typing import Any


class MacsMetadataParser:
    """
    Parse common metadata fields from a MACS source file.
    """

    def parse(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        """
        Parse metadata from one MACS file.

        Parameters
        ----------
        file_path:
            MACS source file to inspect.

        Returns
        -------
        dict[str, Any]:
            Normalized file-level metadata.
        """

        metadata: dict[str, Any] = {
            "run": None,
            "date": None,
            "scenario": None,
            "experiment_condition": None,
            "macs_version": None,
            "source_file_name": None,
            "fep_url": None,
            "fep_version": None,
            "schema_file": None,
            "uss_url": None,
        }

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as macs_file:

            for raw_line in macs_file:

                line = raw_line.strip()

                if not line:
                    continue

                # Once a tab-delimited line appears,
                # the structured MACS header has started.
                if "\t" in line:
                    break

                self._parse_metadata_line(
                    line=line,
                    metadata=metadata,
                )

        return metadata

    def _parse_metadata_line(
        self,
        line: str,
        metadata: dict[str, Any],
    ) -> None:
        """
        Parse one MACS metadata line.

        MACS files are not perfectly consistent in their
        metadata formatting, so known variations are
        normalized here.
        """

        normalized = line.strip()

        lower_line = normalized.lower()

        # --------------------------------------------------
        # Run
        # --------------------------------------------------

        if lower_line == "run":
            metadata["run"] = ""
            return

        if lower_line.startswith("run "):
            metadata["run"] = (
                normalized[4:].strip()
            )
            return

        # --------------------------------------------------
        # Date
        # --------------------------------------------------

        if lower_line.startswith("date "):
            metadata["date"] = (
                normalized[5:].strip()
            )
            return

        # --------------------------------------------------
        # Scenario
        # --------------------------------------------------

        if lower_line.startswith(
            "bundle scenario:"
        ):
            metadata["scenario"] = (
                normalized.split(
                    ":",
                    1,
                )[1].strip()
            )
            return

        if lower_line.startswith("scenario "):
            metadata["scenario"] = (
                normalized[9:].strip()
            )
            return

        # --------------------------------------------------
        # Experiment condition
        # --------------------------------------------------

        if lower_line.startswith(
            "experiment condition"
        ):
            value = normalized[
                len("experiment condition"):
            ].strip(" :")

            metadata[
                "experiment_condition"
            ] = value

            return

        # --------------------------------------------------
        # MACS version
        # --------------------------------------------------

        if lower_line.startswith(
            "macs version"
        ):
            value = normalized[
                len("macs version"):
            ].strip(" :")

            metadata[
                "macs_version"
            ] = value

            return

        # --------------------------------------------------
        # Source file name
        # --------------------------------------------------

        if lower_line.startswith(
            "file name:"
        ):
            metadata[
                "source_file_name"
            ] = normalized.split(
                ":",
                1,
            )[1].strip()

            return

        # --------------------------------------------------
        # FEP URL
        # --------------------------------------------------

        if lower_line.startswith(
            "fep url:"
        ):
            metadata[
                "fep_url"
            ] = normalized.split(
                ":",
                1,
            )[1].strip()

            return

        # --------------------------------------------------
        # FEP version
        # --------------------------------------------------

        if lower_line.startswith(
            "fep version:"
        ):
            metadata[
                "fep_version"
            ] = normalized.split(
                ":",
                1,
            )[1].strip()

            return

        # --------------------------------------------------
        # Schema file
        # --------------------------------------------------

        if lower_line.startswith(
            "schema file"
        ):
            if ":" in normalized:

                metadata[
                    "schema_file"
                ] = normalized.split(
                    ":",
                    1,
                )[1].strip()

            return

        # --------------------------------------------------
        # USS URL
        # --------------------------------------------------

        if lower_line.startswith(
            "uss url:"
        ):
            metadata[
                "uss_url"
            ] = normalized.split(
                ":",
                1,
            )[1].strip()

            return