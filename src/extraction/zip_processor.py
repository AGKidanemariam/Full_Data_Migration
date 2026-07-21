"""
ZIP extraction service.

Responsible for classifying incoming files,
validating ZIP archives,
extracting their contents,
and routing files to the correct destination.
"""

from pathlib import Path
from datetime import datetime
import zipfile

from config.settings import (
    RAW_ZIP_DIR,
    EXTRACTED_DIR,
    ARCHIVE_DIR,
    NON_ZIP_DIR,
    CORRUPTED_DIR,
    FAILED_PROCESSING_DIR,
)

from src.common.file_classifier import is_zip_file
from src.common.file_utils import move_file_safe
from src.common.hash_utils import calculate_sha256
from src.common.logging_utils import get_logger
from src.common.manifest import record_manifest
from src.extraction.zip_validator import validate_zip
from src.extraction.zip_extractor import extract_zip
from src.extraction.zip_archiver import archive_zip
from src.extraction.duplicate_detector import (
    is_duplicate,
    register_hash,
)


logger = get_logger(
    logger_name=__name__,
    stage_name="extract",
)


def process_all_zip_files() -> None:
    """
    Process every file found in the inbox.
    """

    logger.info("Scanning inbox...")

    incoming_files = sorted(RAW_ZIP_DIR.iterdir())

    if not incoming_files:
        logger.info("Inbox is empty.")
        return

    logger.info(
        "Found %s file(s).",
        len(incoming_files),
    )

    for file_path in incoming_files:

        if not file_path.is_file():
            continue

        # -----------------------------
        # Non-ZIP files
        # -----------------------------
        if not is_zip_file(file_path):

            logger.warning(
                "%s is not a ZIP file.",
                file_path.name,
            )

            move_file_safe(
                file_path,
                NON_ZIP_DIR,
            )

            record_manifest(
                run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
                stage="Extract",
                file_name=file_path.name,
                sha256="",
                status="Non-ZIP",
                started_at=datetime.now(),
                finished_at=datetime.now(),
                records_read=0,
                records_written=0,
                records_rejected=0,
                message="Moved to non_zip folder.",
            )

            continue

        process_zip_file(file_path)


def process_zip_file(zip_file: Path) -> None:
    """
    Process one ZIP archive.
    """

    started_at = datetime.now()

    logger.info(
        "Processing %s",
        zip_file.name,
    )

    file_hash = calculate_sha256(zip_file)

    if is_duplicate(file_hash):
        
        logger.warning(
            "%s has already been processed.",
            zip_file.name,
        )

        archive_zip(zip_file)

        record_manifest(
            run_id=started_at.strftime("%Y%m%d_%H%M%S"),
            stage="Extract",
            file_name=zip_file.name,
            sha256=file_hash,
            status="Duplicate",
            started_at=started_at,
            finished_at=datetime.now(),
            records_read=0,
            records_written=0,
            records_rejected=0,
            message="Duplicate ZIP skipped.",
        )
        return
    

    try:

        validate_zip(zip_file)

        output_folder = extract_zip(zip_file)

        archive_zip(zip_file,)
        register_hash(file_hash,) 
        

        record_manifest(
            run_id=started_at.strftime("%Y%m%d_%H%M%S"),
            stage="Extract",
            file_name=zip_file.name,
            sha256=file_hash,
            status="Success",
            started_at=started_at,
            finished_at=datetime.now(),
            records_read=0,
            records_written=0,
            records_rejected=0,
            message=f"Extracted to {output_folder}",
        )

    except zipfile.BadZipFile as error:

        logger.error(str(error))

        move_file_safe(
            zip_file,
            CORRUPTED_DIR,
        )

        record_manifest(
            run_id=started_at.strftime("%Y%m%d_%H%M%S"),
            stage="Extract",
            file_name=zip_file.name,
            sha256=file_hash,
            status="Corrupted",
            started_at=started_at,
            finished_at=datetime.now(),
            records_read=0,
            records_written=0,
            records_rejected=0,
            message=str(error),
        )

    except Exception as error:

        logger.exception(
            "Unexpected processing error."
        )

        move_file_safe(
            zip_file,
            FAILED_PROCESSING_DIR,
        )

        record_manifest(
            run_id=started_at.strftime("%Y%m%d_%H%M%S"),
            stage="Extract",
            file_name=zip_file.name,
            sha256=file_hash,
            status="Failed",
            started_at=started_at,
            finished_at=datetime.now(),
            records_read=0,
            records_written=0,
            records_rejected=0,
            message=str(error),
        )