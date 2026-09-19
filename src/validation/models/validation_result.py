"""
Validation result model.

Represents the outcome of one validation rule
applied to a parsed MACS document or section.
"""

from dataclasses import dataclass
from typing import Literal


ValidationSeverity = Literal[
    "INFO",
    "WARNING",
    "ERROR",
]


@dataclass(slots=True)
class ValidationResult:
    """
    Result produced by one validation rule.

    A validation result records:

    - which rule ran
    - whether it passed
    - severity
    - where the issue occurred
    - a readable message
    """

    rule_name: str

    passed: bool

    severity: ValidationSeverity

    message: str

    section_name: str | None = None

    row_number: int | None = None

    field_name: str | None = None

    expected: str | None = None

    actual: str | None = None