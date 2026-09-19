"""
MACS Trajectory validator.

Applies family-specific validation rules to parsed
Trajectory documents.
"""

from src.inspection.parsers.macs_document import MacsDocument

from src.validation.models.validation_report import ValidationReport
from src.validation.models.validation_result import ValidationResult


class TrajectoryValidator:
    """
    Validate the structure of a MACS Trajectory document.
    """

    REQUIRED_SECTIONS = (
        "GLOBAL_MAP",
        "TRAJPOINT_MAP",
    )

    REQUIRED_COLUMNS = {
        "GLOBAL_MAP": (
            "UTC_TIME",
            "REL_TIME",
            "LOG_TIME",
            "CALLSIGN",
        ),
        "TRAJPOINT_MAP": (
            "UTC_TIME",
            "REL_TIME",
            "LOG_TIME",
            "CALLSIGN",
            "LAT",
            "LONG",
        ),
    }

    NUMERIC_COLUMNS = {
        "GLOBAL_MAP": (
            "REL_TIME",
        ),
        "TRAJPOINT_MAP": (
            "REL_TIME",
            "LAT",
            "LONG",
        ),
    }

    def validate(
        self,
        document: MacsDocument,
        report: ValidationReport | None = None,
    ) -> ValidationReport:
        """
        Run all Trajectory-specific validation rules.
        """

        if report is None:

            report = ValidationReport(
                file_name=document.file_name,
            )

        sections = self._validate_required_sections(
            document=document,
            report=report,
        )

        for section_name, section in sections.items():

            if section is None:
                continue

            self._validate_required_columns(
                section=section,
                section_name=section_name,
                report=report,
            )

            self._validate_numeric_columns(
                section=section,
                section_name=section_name,
                report=report,
            )

        trajpoint_section = sections.get(
            "TRAJPOINT_MAP"
        )

        if trajpoint_section is not None:

            self._validate_latitude(
                section=trajpoint_section,
                report=report,
            )

            self._validate_longitude(
                section=trajpoint_section,
                report=report,
            )

        return report

    def _validate_required_sections(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ) -> dict:
        """
        Confirm all required Trajectory sections exist.
        """

        sections = {}

        for section_name in self.REQUIRED_SECTIONS:

            section = document.get_section(
                section_name
            )

            sections[
                section_name
            ] = section

            if section is not None:

                report.add_result(
                    ValidationResult(
                        rule_name=(
                            "trajectory_required_section"
                        ),
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Required Trajectory section "
                            f"'{section_name}' is present."
                        ),
                        section_name=section_name,
                        expected="section present",
                        actual="present",
                    )
                )

            else:

                report.add_result(
                    ValidationResult(
                        rule_name=(
                            "trajectory_required_section"
                        ),
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Required Trajectory section "
                            f"'{section_name}' is missing."
                        ),
                        section_name=section_name,
                        expected="section present",
                        actual="missing",
                    )
                )

        return sections

    def _validate_required_columns(
        self,
        section,
        section_name: str,
        report: ValidationReport,
    ) -> None:
        """
        Validate required columns for one section.
        """

        required_columns = (
            self.REQUIRED_COLUMNS[
                section_name
            ]
        )

        available_columns = {
            column.strip().upper()
            for column in section.header
        }

        for column_name in required_columns:

            if (
                column_name.upper()
                in available_columns
            ):

                report.add_result(
                    ValidationResult(
                        rule_name=(
                            "trajectory_required_column"
                        ),
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Required column "
                            f"'{column_name}' is present."
                        ),
                        section_name=section_name,
                        field_name=column_name,
                        expected="column present",
                        actual="present",
                    )
                )

            else:

                report.add_result(
                    ValidationResult(
                        rule_name=(
                            "trajectory_required_column"
                        ),
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Required column "
                            f"'{column_name}' is missing."
                        ),
                        section_name=section_name,
                        field_name=column_name,
                        expected="column present",
                        actual="missing",
                    )
                )

    def _validate_numeric_columns(
        self,
        section,
        section_name: str,
        report: ValidationReport,
    ) -> None:
        """
        Validate numeric values in important columns.
        """

        numeric_columns = (
            self.NUMERIC_COLUMNS[
                section_name
            ]
        )

        for column_name in numeric_columns:

            column_index = self._get_column_index(
                section=section,
                column_name=column_name,
            )

            if column_index is None:
                continue

            invalid_rows = []


            for row_number, row in enumerate(
                section.rows,
                start=1,
            ):

                if column_index >= len(row):
                    continue

                value = row[
                    column_index
                ].strip()

                if not value:
                    continue

                try:

                    float(
                        value
                    )

                except ValueError:

                    invalid_rows.append(
                        (
                            row_number,
                            value,
                        )
                    )

            if not invalid_rows:

                report.add_result(
                    ValidationResult(
                        rule_name=(
                            "trajectory_numeric_field"
                        ),
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Column '{column_name}' "
                            "contains valid numeric values."
                        ),
                        section_name=section_name,
                        field_name=column_name,
                    )
                )

                continue

            for row_number, value in invalid_rows:

                report.add_result(
                    ValidationResult(
                        rule_name=(
                            "trajectory_numeric_field"
                        ),
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Column '{column_name}' "
                            "contains a non-numeric value."
                        ),
                        section_name=section_name,
                        row_number=row_number,
                        field_name=column_name,
                        expected="numeric value",
                        actual=value,
                    )
                )

    def _validate_latitude(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Validate geographic latitude range.
        """

        self._validate_range(
            section=section,
            column_name="LAT",
            minimum=-90.0,
            maximum=90.0,
            rule_name="trajectory_latitude_range",
            report=report,
        )

    def _validate_longitude(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Validate geographic longitude range.
        """

        self._validate_range(
            section=section,
            column_name="LONG",
            minimum=-180.0,
            maximum=180.0,
            rule_name="trajectory_longitude_range",
            report=report,
        )

    def _validate_range(
        self,
        section,
        column_name: str,
        minimum: float,
        maximum: float,
        rule_name: str,
        report: ValidationReport,
    ) -> None:
        """
        Validate that numeric values fall within
        a specified range.
        """

        column_index = self._get_column_index(
            section=section,
            column_name=column_name,
        )

        if column_index is None:
            return

        invalid_rows = []

        for row_number, row in enumerate(
            section.rows,
            start=1,
        ):

            if column_index >= len(row):
                continue

            value = row[
                column_index
            ].strip()

            if not value:
                continue

            try:

                numeric_value = float(
                    value
                )

            except ValueError:
                continue

            if not (
                minimum
                <= numeric_value
                <= maximum
            ):

                invalid_rows.append(
                    (
                        row_number,
                        value,
                    )
                )

        if not invalid_rows:

            report.add_result(
                ValidationResult(
                    rule_name=rule_name,
                    passed=True,
                    severity="INFO",
                    message=(
                        f"All populated {column_name} "
                        "values are within the valid range."
                    ),
                    section_name=section.name,
                    field_name=column_name,
                    expected=(
                        f"{minimum} <= "
                        f"{column_name} <= {maximum}"
                    ),
                    actual="valid",
                )
            )

            return

        for row_number, value in invalid_rows:

            report.add_result(
                ValidationResult(
                    rule_name=rule_name,
                    passed=False,
                    severity="ERROR",
                    message=(
                        f"{column_name} is outside "
                        "the valid geographic range."
                    ),
                    section_name=section.name,
                    row_number=row_number,
                    field_name=column_name,
                    expected=(
                        f"{minimum} <= "
                        f"{column_name} <= {maximum}"
                    ),
                    actual=value,
                )
            )

    def _get_column_index(
        self,
        section,
        column_name: str,
    ) -> int | None:
        """
        Find a column using case-insensitive matching.
        """

        requested_name = (
            column_name
            .strip()
            .upper()
        )

        for index, header_name in enumerate(
            section.header
        ):

            if (
                header_name
                .strip()
                .upper()
                == requested_name
            ):

                return index

        return None                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  