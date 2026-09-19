"""
FlightState validator.

Applies FlightState-specific validation rules
to a parsed MACS document.
"""

from src.inspection.parsers.macs_document import MacsDocument
from src.validation.models.validation_report import ValidationReport
from src.validation.models.validation_result import ValidationResult


class FlightStateValidator:
    """
    Validate the structure and core fields expected
    in a MACS FlightState document.
    """

    REQUIRED_COLUMNS = (
        "UTC_TIME",
        "REL_TIME",
        "LOG_TIME",
        "CALLSIGN",
        "FLIGHT_RULES",
        "STAMP_TIME",
        "SIM_TIME",
        "LAT",
        "LONG",
        "X",
        "Y",
        "ALT",
    )

    NUMERIC_COLUMNS = (
        "REL_TIME",
        "SIM_TIME",
        "LAT",
        "LONG",
        "X",
        "Y",
        "ALT",
    )

    def validate(
        self,
        document: MacsDocument,
        report: ValidationReport | None = None,
    ) -> ValidationReport:
        """
        Run all FlightState-specific validation rules.

        If a report already exists, results are added
        to that report. Otherwise a new report is created.
        """

        if report is None:

            report = ValidationReport(
                file_name=document.file_name,
            )

        section = self._get_flightstate_section(
            document=document,
            report=report,
        )

        if section is None:
            return report

        self._validate_required_columns(
            section=section,
            report=report,
        )

        self._validate_callsigns(
            section=section,
            report=report,
        )

        self._validate_numeric_columns(
            section=section,
            report=report,
        )

        self._validate_latitude(
            section=section,
            report=report,
        )

        self._validate_longitude(
            section=section,
            report=report,
        )

        return report

    def _get_flightstate_section(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ):
        """
        Locate the FlightState section.
        """

        section = document.get_section(
            "FlightState"
        )

        if section is not None:

            report.add_result(
                ValidationResult(
                    rule_name="flightstate_section_exists",
                    passed=True,
                    severity="INFO",
                    message="FlightState section found.",
                    section_name="FlightState",
                )
            )

            return section

        report.add_result(
            ValidationResult(
                rule_name="flightstate_section_exists",
                passed=False,
                severity="ERROR",
                message=(
                    "FlightState document does not contain "
                    "a FlightState section."
                ),
                section_name="FlightState",
                expected="FlightState section",
                actual="missing",
            )
        )

        return None

    def _validate_required_columns(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Confirm required FlightState columns exist.
        """

        available_columns = {
            column.strip().upper()
            for column in section.header
        }

        for column in self.REQUIRED_COLUMNS:

            if column.upper() in available_columns:

                report.add_result(
                    ValidationResult(
                        rule_name="flightstate_required_column",
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Required FlightState column "
                            f"'{column}' is present."
                        ),
                        section_name=section.name,
                        field_name=column,
                        expected="column present",
                        actual="present",
                    )
                )

            else:

                report.add_result(
                    ValidationResult(
                        rule_name="flightstate_required_column",
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Required FlightState column "
                            f"'{column}' is missing."
                        ),
                        section_name=section.name,
                        field_name=column,
                        expected="column present",
                        actual="missing",
                    )
                )

    def _validate_callsigns(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Confirm CALLSIGN values are not empty.
        """

        callsign_index = self._get_column_index(
            section=section,
            column_name="CALLSIGN",
        )

        if callsign_index is None:
            return

        missing_callsigns: list[int] = []

        for row_number, row in enumerate(
            section.rows,
            start=1,
        ):

            if callsign_index >= len(row):
                continue

            value = row[
                callsign_index
            ].strip()

            if not value:

                missing_callsigns.append(
                    row_number,
                )

        if not missing_callsigns:

            report.add_result(
                ValidationResult(
                    rule_name="flightstate_callsign_not_empty",
                    passed=True,
                    severity="INFO",
                    message=(
                        "All FlightState rows contain "
                        "a CALLSIGN value."
                    ),
                    section_name=section.name,
                    field_name="CALLSIGN",
                )
            )

            return

        for row_number in missing_callsigns:

            report.add_result(
                ValidationResult(
                    rule_name="flightstate_callsign_not_empty",
                    passed=False,
                    severity="ERROR",
                    message="CALLSIGN is empty.",
                    section_name=section.name,
                    row_number=row_number,
                    field_name="CALLSIGN",
                    expected="non-empty value",
                    actual="<empty>",
                )
            )

    def _validate_numeric_columns(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Confirm important numeric fields contain
        valid numeric values when populated.
        """

        for column_name in self.NUMERIC_COLUMNS:

            column_index = self._get_column_index(
                section=section,
                column_name=column_name,
            )

            if column_index is None:
                continue

            invalid_rows: list[
                tuple[int, str]
            ] = []

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
                        rule_name="flightstate_numeric_field",
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Column '{column_name}' "
                            "contains valid numeric values."
                        ),
                        section_name=section.name,
                        field_name=column_name,
                    )
                )

                continue

            for (
                row_number,
                value,
            ) in invalid_rows:

                report.add_result(
                    ValidationResult(
                        rule_name="flightstate_numeric_field",
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Column '{column_name}' "
                            "contains a non-numeric value."
                        ),
                        section_name=section.name,
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
        Confirm latitude values fall within
        the valid geographic range.
        """

        column_index = self._get_column_index(
            section=section,
            column_name="LAT",
        )

        if column_index is None:
            return

        invalid_rows: list[
            tuple[int, str]
        ] = []

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

                latitude = float(
                    value
                )

            except ValueError:
                continue

            if not (
                -90.0
                <= latitude
                <= 90.0
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
                    rule_name="flightstate_latitude_range",
                    passed=True,
                    severity="INFO",
                    message=(
                        "All populated LAT values are "
                        "within -90 and 90."
                    ),
                    section_name=section.name,
                    field_name="LAT",
                    expected="-90 <= LAT <= 90",
                    actual="valid",
                )
            )

            return

        for (
            row_number,
            value,
        ) in invalid_rows:

            report.add_result(
                ValidationResult(
                    rule_name="flightstate_latitude_range",
                    passed=False,
                    severity="ERROR",
                    message=(
                        "Latitude is outside the valid "
                        "geographic range."
                    ),
                    section_name=section.name,
                    row_number=row_number,
                    field_name="LAT",
                    expected="-90 <= LAT <= 90",
                    actual=value,
                )
            )

    def _validate_longitude(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Confirm longitude values fall within
        the valid geographic range.
        """

        column_index = self._get_column_index(
            section=section,
            column_name="LONG",
        )

        if column_index is None:
            return

        invalid_rows: list[
            tuple[int, str]
        ] = []

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

                longitude = float(
                    value
                )

            except ValueError:
                continue

            if not (
                -180.0
                <= longitude
                <= 180.0
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
                    rule_name="flightstate_longitude_range",
                    passed=True,
                    severity="INFO",
                    message=(
                        "All populated LONG values are "
                        "within -180 and 180."
                    ),
                    section_name=section.name,
                    field_name="LONG",
                    expected="-180 <= LONG <= 180",
                    actual="valid",
                )
            )

            return

        for (
            row_number,
            value,
        ) in invalid_rows:

            report.add_result(
                ValidationResult(
                    rule_name="flightstate_longitude_range",
                    passed=False,
                    severity="ERROR",
                    message=(
                        "Longitude is outside the valid "
                        "geographic range."
                    ),
                    section_name=section.name,
                    row_number=row_number,
                    field_name="LONG",
                    expected="-180 <= LONG <= 180",
                    actual=value,
                )
            )

    def _get_column_index(
        self,
        section,
        column_name: str,
    ) -> int | None:
        """
        Locate a column by name using
        case-insensitive matching.
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
