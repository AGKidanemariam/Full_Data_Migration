"""
MACS metadata validator.

Validates required file-level metadata extracted
from a parsed MacsDocument.
"""

from src.inspection.parsers.macs_document import MacsDocument
from src.validation.models.validation_report import ValidationReport
from src.validation.models.validation_result import ValidationResult


class MetadataValidator:
    """
    Validate common MACS metadata fields.
    """

    REQUIRED_FIELDS = (
        "date",
        "scenario",
        "macs_version",
        "source_file_name",
    )

    OPTIONAL_FIELDS = (
        "run",
        "experiment_condition",
        "fep_url",
        "fep_version",
        "schema_file",
        "uss_url",
    )

    def validate(
        self,
        document: MacsDocument,
        report: ValidationReport | None = None,
    ) -> ValidationReport:
        """
        Validate MACS metadata.

        If an existing report is supplied, results are
        appended to that report. Otherwise a new report
        is created.
        """

        if report is None:

            report = ValidationReport(
                file_name=document.file_name,
            )

        self._validate_required_fields(
            document=document,
            report=report,
        )

        self._validate_optional_fields(
            document=document,
            report=report,
        )

        return report

    def _validate_required_fields(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ) -> None:
        """
        Confirm required metadata fields are present.
        """

        for field_name in self.REQUIRED_FIELDS:

            value = document.metadata.get(
                field_name,
            )

            if self._has_value(
                value,
            ):

                report.add_result(
                    ValidationResult(
                        rule_name="required_metadata",
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Required metadata field "
                            f"'{field_name}' is present."
                        ),
                        field_name=field_name,
                        expected="non-empty value",
                        actual=str(
                            value
                        ),
                    )
                )

            else:

                report.add_result(
                    ValidationResult(
                        rule_name="required_metadata",
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Required metadata field "
                            f"'{field_name}' is missing "
                            "or empty."
                        ),
                        field_name=field_name,
                        expected="non-empty value",
                        actual=self._display_value(
                            value,
                        ),
                    )
                )

    def _validate_optional_fields(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ) -> None:
        """
        Record missing optional metadata as warnings.

        Optional fields do not block the pipeline.
        """

        for field_name in self.OPTIONAL_FIELDS:

            value = document.metadata.get(
                field_name,
            )

            if self._has_value(
                value,
            ):

                report.add_result(
                    ValidationResult(
                        rule_name="optional_metadata",
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Optional metadata field "
                            f"'{field_name}' is present."
                        ),
                        field_name=field_name,
                        actual=str(
                            value
                        ),
                    )
                )

            else:

                report.add_result(
                    ValidationResult(
                        rule_name="optional_metadata",
                        passed=False,
                        severity="WARNING",
                        message=(
                            f"Optional metadata field "
                            f"'{field_name}' is missing "
                            "or empty."
                        ),
                        field_name=field_name,
                        expected="value when available",
                        actual=self._display_value(
                            value,
                        ),
                    )
                )

    def _has_value(
        self,
        value,
    ) -> bool:
        """
        Return True when a metadata value is meaningful.
        """

        if value is None:
            return False

        if isinstance(
            value,
            str,
        ):

            return bool(
                value.strip()
            )

        return True

    def _display_value(
        self,
        value,
    ) -> str:
        """
        Convert an empty metadata value into a readable
        validation-report value.
        """

        if value is None:
            return "None"

        if isinstance(
            value,
            str,
        ) and not value.strip():

            return "<empty>"

        return str(
            value
        )