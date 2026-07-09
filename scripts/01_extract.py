from pathlib import Path
import zipfile
import shutil
import logging
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_ZIP_DIR = BASE_DIR / "raw_zips"
EXTRACTED_DIR = BASE_DIR / "extracted"
REJECTED_DIR = BASE_DIR / "rejected"
ARCHIVE_DIR = BASE_DIR / "archive"
LOG_DIR = BASE_DIR / "logs"

for folder in [RAW_ZIP_DIR, EXTRACTED_DIR, REJECTED_DIR, ARCHIVE_DIR, LOG_DIR]:
    folder.mkdir(exist_ok=True)

log_file = LOG_DIR / f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def move_file_safe(source_path, destination_folder):
    destination_path = destination_folder / source_path.name

    if destination_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination_path = destination_folder / f"{source_path.stem}_{timestamp}{source_path.suffix}"

    shutil.move(str(source_path), str(destination_path))
    return destination_path


zip_files = list(RAW_ZIP_DIR.glob("*.zip"))

if not zip_files:
    print("No ZIP files found in raw_zips.")
    logging.info("No ZIP files found in raw_zips.")

for zip_path in zip_files:
    output_folder = EXTRACTED_DIR / zip_path.stem

    try:
        print(f"Processing: {zip_path.name}")
        logging.info(f"Processing ZIP file: {zip_path.name}")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            bad_file = zip_ref.testzip()

            if bad_file:
                print(f"Rejected: {zip_path.name}")
                print(f"Problem file inside ZIP: {bad_file}")

                logging.error(f"Rejected {zip_path.name}. Bad file inside ZIP: {bad_file}")

                rejected_path = move_file_safe(zip_path, REJECTED_DIR)
                logging.info(f"Moved rejected ZIP to: {rejected_path}")
                continue

            output_folder.mkdir(exist_ok=True)
            zip_ref.extractall(output_folder)

        archived_path = move_file_safe(zip_path, ARCHIVE_DIR)

        print(f"Extracted: {zip_path.name} -> {output_folder}")
        print(f"Archived ZIP -> {archived_path}")

        logging.info(f"Extracted {zip_path.name} to {output_folder}")
        logging.info(f"Archived ZIP to {archived_path}")

    except zipfile.BadZipFile:
        print(f"Rejected: {zip_path.name}. The ZIP file is corrupted.")
        logging.error(f"Rejected {zip_path.name}. BadZipFile error.")

        rejected_path = move_file_safe(zip_path, REJECTED_DIR)
        logging.info(f"Moved rejected ZIP to: {rejected_path}")

    except Exception as error:
        print(f"Failed to process {zip_path.name}: {error}")
        logging.exception(f"Unexpected error while processing {zip_path.name}")

        rejected_path = move_file_safe(zip_path, REJECTED_DIR)
        logging.info(f"Moved failed ZIP to: {rejected_path}")