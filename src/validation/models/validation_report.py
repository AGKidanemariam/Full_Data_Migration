"""
Validation report model.

Collects all validation results produced
for one parsed source document.
"""

from dataclasses import dataclass, field

from src.validation.models.validation_result import (
    ValidationResult,
)


@dataclass(slots=True)
class ValidationReport:
    """
    Complete validation report for one file.

    The report stores every ValidationResult
    and determines whether the document is
    allowed to continue through the pipeline.
    """

    file_name: str

    results: list[ValidationResult] = field(
        default_factory=list,
    )

    def add_result(
        self,
        result: ValidationResult,
    ) -> None:
        """
        Add one validation result to the report.
        """

        self.results.append(
            result,
        )

    @property
    def error_count(self) -> int:
        """
        Return the number of failed ERROR results.
        """

        return sum(
            1
            for result in self.results
            if (
                not result.passed
                and result.severity == "ERROR"
            )
        )

    @property
    def warning_count(self) -> int:
        """
        Return the number of failed WARNING results.
        """

        return sum(
            1
            for result in self.results
            if (
                not result.passed
                and result.severity == "WARNING"
            )
        )

    @property
    def info_count(self) -> int:
        """
        Return the number of INFO results.
        """

        return sum(
            1
            for result in self.results
            if result.severity == "INFO"
        )

    @property
    def passed_count(self) -> int:
        """
        Return the number of successful rules.
        """

        return sum(
            1
            for result in self.results
            if result.passed
        )

    @property
    def failed_count(self) -> int:
        """
        Return the number of failed rules.
        """

        return sum(
            1
            for result in self.results
            if not result.passed
        )

    @property
    def is_valid(self) -> bool:
        """
        Return True when no blocking validation
        errors were detected.

        Warnings do not block the pipeline.
        """

        return self.error_count == 0

    @property
    def status(self) -> str:
        """
        Return the overall validation status.
        """

        if self.error_count > 0:
            return "FAILED"

        if self.warning_count > 0:
            return "PASSED_WITH_WARNINGS"

        return "PASSED"

    def summary(
        self,
    ) -> dict[str, int | str | bool]:
        """
        Return a compact validation summary.
        """

        return {
            "file_name": self.file_name,
            "status": self.status,
            "is_valid": self.is_valid,
            "total_results": len(
                self.results
            ),
            "passed": self.passed_count,
            "failed": self.failed_count,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
        }