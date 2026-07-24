"""
Inspection stage orchestrator.

Coordinates the inspection of all extracted files.
"""

from src.common.logging_utils import get_logger
from src.common.models.data_profile import DataProfile

from src.inspection.file_discovery import discover_files
from src.inspection.file_inspector import inspect_file
from src.inspection.inspection_report import save_inspection_report


logger = get_logger(
    logger_name=__name__,
    stage_name="inspection",
)


def inspect_all_files() -> None:
    """
    Inspect every extracted file and save the results.
    """

    logger.info(
        "Starting inspection stage."
    )

    discovered_files = discover_files()

    logger.info(
        "Preparing to inspect %s file(s).",
        len(discovered_files),
    )

    inspection_results: list[DataProfile] = []

    for file_path in discovered_files:

        profile = inspect_file(
            file_path,
        )

        inspection_results.append(
            profile,
        )

        logger.info(
            "Inspection completed for %s.",
            profile.file_name,
        )

    save_inspection_report(
        inspection_results,
    )

    logger.info(
        "Inspection stage completed. Report contains %s record(s).",
        len(inspection_results),
    )