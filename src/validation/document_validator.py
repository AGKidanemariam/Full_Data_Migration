"""
MACS document validator.

Runs structural validation rules against a parsed
MacsDocument and returns a ValidationReport.
"""

from src.inspection.parsers.macs_document import MacsDocument
from src.validation.models.validation_report import ValidationReport
from src.validation.models.validation_result import ValidationResult


class DocumentValidator:
    """
    Validate the overall structure of a parsed MACS document.
    """

    def validate(
        self,
        document: MacsDocument,
    ) -> ValidationReport:
        """
        Run all document-level and section-level
        structural validation rules.
        """

        report = ValidationReport(
            file_name=document.file_name,
        )

        self._validate_parser_warnings(
            document=document,
            report=report,
        )

        self._validate_sections_exist(
            document=document,
            report=report,
        )

        for section in document.sections:

            self._validate_header_exists(
                section=section,
                report=report,
            )

            self._validate_duplicate_columns(
                section=section,
                report=report,
            )

            self._validate_section_rows(
                section=section,
                report=report,
            )

            self._validate_row_lengths(
                section=section,
                report=report,
            )

        return report

    def _validate_parser_warnings(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ) -> None:
        """
        Check whether parsing generated warnings.
        """

        if not document.warnings:

            report.add_result(
                ValidationResult(
                    rule_name="parser_warnings",
                    passed=True,
                    severity="INFO",
                    message="No parser warnings detected.",
                )
            )

            return

        for warning in document.warnings:

            report.add_result(
                ValidationResult(
                    rule_name="parser_warnings",
                    passed=False,
                    severity="WARNING",
                    message=warning,
                )
            )

    def _validate_sections_exist(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ) -> None:
        """
        Confirm that at least one parsed section exists.
        """

        if document.sections:

            report.add_result(
                ValidationResult(
                    rule_name="sections_exist",
                    passed=True,
                    severity="INFO",
                    message=(
                        f"{len(document.sections)} "
                        "parsed section(s) found."
                    ),
                    expected="at least 1",
                    actual=str(
                        len(document.sections)
                    ),
                )
            )

            return

        report.add_result(
            ValidationResult(
                rule_name="sections_exist",
                passed=False,
                severity="ERROR",
                message="No parsed sections were found.",
                expected="at least 1",
                actual="0",
            )
        )

    def _validate_header_exists(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Confirm that a section contains a header.
        """

        if section.header:

            report.add_result(
                ValidationResult(
                    rule_name="header_exists",
                    passed=True,
                    severity="INFO",
                    message=(
                        f"Header contains "
                        f"{section.column_count} column(s)."
                    ),
                    section_name=section.name,
                    expected="at least 1 column",
                    actual=str(
                        section.column_count
                    ),
                )
            )

            return

        report.add_result(
            ValidationResult(
                rule_name="header_exists",
                passed=False,
                severity="ERROR",
                message="Section does not contain a header.",
                section_name=section.name,
                expected="at least 1 column",
                actual="0",
            )
        )

    def _validate_duplicate_columns(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Detect duplicate column names in a section header.
        """

        seen: set[str] = set()

        duplicates: list[str] = []

        for column in section.header:

            normalized = column.strip().lower()

            if normalized in seen:

                duplicates.append(
                    column,
                )

            else:

                seen.add(
                    normalized,
                )

        if not duplicates:

            report.add_result(
                ValidationResult(
                    rule_name="duplicate_columns",
                    passed=True,
                    severity="INFO",
                    message="No duplicate columns detected.",
                    section_name=section.name,
                )
            )

            return

        report.add_result(
            ValidationResult(
                rule_name="duplicate_columns",
                passed=False,
                severity="ERROR",
                message=(
                    "Duplicate column names detected: "
                    + ", ".join(duplicates)
                ),
                section_name=section.name,
                expected="unique column names",
                actual=", ".join(
                    duplicates
                ),
            )
        )

    def _validate_section_rows(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Check whether a parsed section contains data rows.
        """

        if section.rows:

            report.add_result(
                ValidationResult(
                    rule_name="section_has_rows",
                    passed=True,
                    severity="INFO",
                    message=(
                        f"Section contains "
                        f"{section.row_count} row(s)."
                    ),
                    section_name=section.name,
                    expected="at least 1 row",
                    actual=str(
                        section.row_count
                    ),
                )
            )

            return

        report.add_result(
            ValidationResult(
                rule_name="section_has_rows",
                passed=False,
                severity="WARNING",
                message="Section contains no data rows.",
                section_name=section.name,
                expected="at least 1 row",
                actual="0",
            )
        )

    def _validate_row_lengths(
        self,
        section,
        report: ValidationReport,
    ) -> None:
        """
        Confirm every row contains the same number
        of fields as the section header.
        """

        expected_count = section.column_count

        if expected_count == 0:
            return

        mismatches: list[
            tuple[int, int]
        ] = []

        for row_number, row in enumerate(
            section.rows,
            start=1,
        ):

            actual_count = len(row)

            if actual_count != expected_count:

                mismatches.append(
                    (
                        row_number,
                        actual_count,
                    )
                )

        if not mismatches:

            report.add_result(
                ValidationResult(
                    rule_name="row_length_matches_header",
                    passed=True,
                    severity="INFO",
                    message=(
                        f"All {section.row_count} row(s) "
                        "match the header field count."
                    ),
                    section_name=section.name,
                    expected=str(
                        expected_count
                    ),
                    actual=str(
                        expected_count
                    ),
                )
            )

            return

        for (
            row_number,
            actual_count,
        ) in mismatches:

            report.add_result(
                ValidationResult(
                    rule_name="row_length_matches_header",
                    passed=False,
                    severity="ERROR",
                    message=(
                        f"Row contains {actual_count} "
                        f"field(s), but header contains "
                        f"{expected_count}."
                    ),
                    section_name=section.name,
                    row_number=row_number,
                    expected=str(
                        expected_count
                    ),
                    actual=str(
                        actual_count
                    ),
                )
            )