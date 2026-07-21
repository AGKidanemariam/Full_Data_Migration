"""
ZIP extraction utilities.

Responsible for extracting validated ZIP archives.
"""

from pathlib import Path
import zipfile

from config.settings import EXTRACTED_DIR
from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="extract",
)


def extract_zip(zip_file: Path) -> Path:
    """
    Extract a validated ZIP archive.

    Parameters
    ----------
    zip_file
        The validated ZIP file.

    Returns
    -------
    Path
        The folder where the ZIP was extracted.
    """

    logger.info(
        "Extracting %s",
        zip_file.name,
    )

    output_folder = EXTRACTED_DIR / zip_file.stem

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        zip_file,
        "r",
    ) as zip_ref:

        zip_ref.extractall(output_folder)

    logger.info(
        "Extraction complete: %s",
        output_folder,
    )

    return output_folder