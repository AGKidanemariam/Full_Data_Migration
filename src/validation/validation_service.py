"""
MACS validation service.

Coordinates generic and family-specific validation
for parsed MACS documents.
"""

from src.inspection.parsers.macs_document import MacsDocument

from src.validation.document_validator import DocumentValidator
from src.validation.metadata_validator import MetadataValidator
from src.validation.family.flightstate_validator import (
    FlightStateValidator,
)

from src.validation.models.validation_report import (
    ValidationReport,
)
from src.validation.models.validation_result import (
    ValidationResult,
)


class MacsValidationService:
    """
    Main validation orchestrator for MACS documents.

    Every document receives:

    1. Structural validation
    2. Metadata validation
    3. Family-specific validation when supported
    """

    def __init__(self) -> None:
        """
        Initialize validator components.
        """

        self.document_validator = (
            DocumentValidator()
        )

        self.metadata_validator = (
            MetadataValidator()
        )

        self.family_validators = {
            "flightstate": FlightStateValidator(),
        }

    def validate(
        self,
        document: MacsDocument,
    ) -> ValidationReport:
        """
        Run the complete validation workflow.

        Parameters
        ----------
        document:
            Parsed MACS document to validate.

        Returns
        -------
        ValidationReport:
            Combined results from all applicable
            validation layers.
        """

        # --------------------------------------------------
        # 1. Generic structural validation
        # --------------------------------------------------

        report = (
            self.document_validator.validate(
                document
            )
        )

        # --------------------------------------------------
        # 2. Common metadata validation
        # --------------------------------------------------

        self.metadata_validator.validate(
            document=document,
            report=report,
        )

        # --------------------------------------------------
        # 3. Family-specific validation
        # --------------------------------------------------

        self._run_family_validator(
            document=document,
            report=report,
        )

        return report

    def _run_family_validator(
        self,
        document: MacsDocument,
        report: ValidationReport,
    ) -> None:
        """
        Run the validator associated with the
        MACS document family.
        """

        normalized_family = (
            document.macs_family
            .strip()
            .lower()
        )

        validator = (
            self.family_validators.get(
                normalized_family
            )
        )

        if validator is None:

            report.add_result(
                ValidationResult(
                    rule_name=(
                        "family_validator_available"
                    ),
                    passed=False,
                    severity="WARNING",
                    message=(
                        "No family-specific validator "
                        f"is currently registered for "
                        f"'{document.macs_family}'."
                    ),
                    expected=(
                        "registered family validator"
                    ),
                    actual=document.macs_family,
                )
            )

            return

        report.add_result(
            ValidationResult(
                rule_name=(
                    "family_validator_available"
                ),
                passed=True,
                severity="INFO",
                message=(
                    "Family-specific validator found "
                    f"for '{document.macs_family}'."
                ),
                expected=(
                    "registered family validator"
                ),
                actual=document.macs_family,
            )
        )

        validator.validate(
            document=document,
            report=report,
        )
