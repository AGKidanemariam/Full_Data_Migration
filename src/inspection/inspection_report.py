"""
Inspection report writer.

Writes inspection results to a CSV report.
"""

from dataclasses import asdict
from pathlib import Path
import csv

from config.settings import METADATA_DIR

from src.common.models.data_profile import DataProfile
from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="inspection",
)


REPORT_FILE = (
    METADATA_DIR /
    "inspection_report.csv"
)


def save_inspection_report(
    profiles: list[DataProfile],
) -> None:
    """
    Save inspection results to a CSV report.
    """

    if not profiles:

        logger.warning(
            "No inspection results to save."
        )

        return

    rows = [
        asdict(profile)
        for profile in profiles
    ]

    fieldnames = list(
        rows[0].keys()
    )

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        REPORT_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as report:

        writer = csv.DictWriter(
            report,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(rows)

    logger.info(
        "Inspection report written to %s",
        REPORT_FILE,
    )