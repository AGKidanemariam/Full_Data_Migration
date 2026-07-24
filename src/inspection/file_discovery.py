"""
File discovery utilities.

Responsible for locating every extracted file
inside the extraction directory.
"""

from pathlib import Path

from config.settings import EXTRACTED_DIR
from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="inspection",
)


def discover_files() -> list[Path]:
    """
    Discover every extracted file.

    Returns
    -------
    list[Path]
        Every file found recursively inside
        the extracted directory.
    """

    logger.info(
        "Scanning extracted directory..."
    )

    discovered_files = sorted(
        file_path
        for file_path in EXTRACTED_DIR.rglob("*")
        if file_path.is_file()
    )

    logger.info(
        "Discovered %s file(s).",
        len(discovered_files),
    )

    return discovered_files