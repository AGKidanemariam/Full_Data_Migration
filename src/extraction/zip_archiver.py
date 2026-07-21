"""
ZIP archiving utilities.

Responsible for moving successfully
processed ZIP files into the archive.
"""

from pathlib import Path

from config.settings import ARCHIVE_DIR
from src.common.file_utils import move_file_safe
from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="extract",
)


def archive_zip(zip_file: Path) -> Path:
    """
    Archive a successfully processed ZIP file.

    Parameters
    ----------
    zip_file
        ZIP file to archive.

    Returns
    -------
    Path
        Destination of the archived ZIP.
    """

    logger.info(
        "Archiving %s",
        zip_file.name,
    )

    archived_path = move_file_safe(
        zip_file,
        ARCHIVE_DIR,
    )

    logger.info(
        "Archived to %s",
        archived_path,
    )

    return archived_path