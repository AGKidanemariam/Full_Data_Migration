"""
ZIP validation utilities.

Responsible for verifying that a ZIP archive
is structurally valid before extraction.
"""

from pathlib import Path
import zipfile

from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="extract",
)


def validate_zip(zip_file: Path) -> None:
    """
    Validate the integrity of a ZIP archive.

    Parameters
    ----------
    zip_file
        ZIP archive to validate.

    Raises
    ------
    zipfile.BadZipFile
        Raised when the archive is corrupted.
    """

    logger.info(
        "Validating %s",
        zip_file.name,
    )

    with zipfile.ZipFile(
        zip_file,
        "r",
    ) as zip_ref:

        bad_file = zip_ref.testzip()

    if bad_file:

        raise zipfile.BadZipFile(
            f"Corrupted file inside ZIP: {bad_file}"
        )

    logger.info(
        "%s passed validation.",
        zip_file.name,
    )
