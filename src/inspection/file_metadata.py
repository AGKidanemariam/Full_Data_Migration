"""
File metadata utilities.

Responsible for collecting metadata
about one discovered file.
"""

from pathlib import Path
from datetime import datetime

from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="inspection",
)


def get_file_metadata(file_path: Path) -> dict:
    """
    Collect metadata about one file.

    Parameters
    ----------
    file_path
        File to inspect.

    Returns
    -------
    dict
        Metadata describing the file.
    """

    logger.info(
        "Collecting metadata for %s",
        file_path.name,
    )

    stats = file_path.stat()

    metadata = {
        "file_name": file_path.name,
        "file_stem": file_path.stem,
        "extension": file_path.suffix.lower(),
        "parent_folder": file_path.parent.name,
        "absolute_path": str(file_path.resolve()),
        "size_bytes": stats.st_size,
        "created_at": datetime.fromtimestamp(
            stats.st_ctime,
        ),
        "modified_at": datetime.fromtimestamp(
            stats.st_mtime,
        ),
        "exists": file_path.exists(),
    }

    logger.info(
        "Metadata collected for %s",
        file_path.name,
    )

    return metadata