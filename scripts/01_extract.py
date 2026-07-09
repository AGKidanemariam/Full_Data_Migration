# ============================================================
# IMPORT LIBRARIES
# ============================================================

# Path = Safer way to work with files and folders across Windows, Mac, and Linux.
from pathlib import Path

# Built-in Python library used to read, validate, and extract ZIP files.
import zipfile

# Used to move, copy, and manage files and folders.
import shutil

# Used to create log files instead of only printing messages to the screen.
import logging

# Used to generate timestamps for log files and duplicate filenames.
from datetime import datetime


# ============================================================
# FIND THE PROJECT ROOT DIRECTORY
# ============================================================

# __file__ = the current Python file (01_extract.py)
# resolve() = convert to the full absolute path
# parent = move up one folder (scripts)
# parent.parent = move up another folder (data_project)
#
# Result:
# C:\Users\akidanem\data_project
BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# CREATE PATH OBJECTS FOR ALL PROJECT FOLDERS
# ============================================================

# These DO NOT create folders.
# They simply tell Python where each folder is located.

RAW_ZIP_DIR = BASE_DIR / "raw_zips"      # Incoming ZIP files waiting to be processed

EXTRACTED_DIR = BASE_DIR / "extracted"   # Successfully extracted contents

REJECTED_DIR = BASE_DIR / "rejected"     # Corrupted or failed ZIP files

ARCHIVE_DIR = BASE_DIR / "archive"       # Successfully processed ZIP files

LOG_DIR = BASE_DIR / "logs"              # Log files created during every ETL run


# ============================================================
# CREATE FOLDERS IF THEY DON'T ALREADY EXIST
# ============================================================

# Instead of writing mkdir() five separate times,
# loop through every folder.

for folder in [RAW_ZIP_DIR,
               EXTRACTED_DIR,
               REJECTED_DIR,
               ARCHIVE_DIR,
               LOG_DIR]:

    # mkdir() = Make Directory
    #
    # exist_ok=True means:
    # "If the folder already exists, don't throw an error."
    folder.mkdir(exist_ok=True)


# ============================================================
# CREATE A UNIQUE LOG FILE
# ============================================================

# datetime.now() gets the current date and time.
#
# strftime() formats it into:
#
# 20260709_184500
#
# Final filename becomes:
#
# logs/extract_20260709_184500.log

log_file = LOG_DIR / f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


# ============================================================
# CONFIGURE THE LOGGING SYSTEM
# ============================================================

logging.basicConfig(

    # Save every log message into this file.
    filename=log_file,

    # Record INFO messages and anything more severe.
    level=logging.INFO,

    # Format every log line like:
    #
    # 2026-07-09 18:45:02 INFO Extracted customers.zip
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ============================================================
# FUNCTION TO MOVE FILES SAFELY
# ============================================================

# Functions are reusable blocks of code.
#
# Instead of writing file-moving logic everywhere,
# we write it once and reuse it.

def move_file_safe(source_path, destination_folder):

    # Build the destination path.
    #
    # Example:
    #
    # archive/customers.zip
    destination_path = destination_folder / source_path.name


    # Check if that filename already exists.
    if destination_path.exists():

        # Create a timestamp.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Rename the file instead of overwriting it.
        #
        # customers.zip
        #
        # becomes
        #
        # customers_20260709_184530.zip
        destination_path = destination_folder / f"{source_path.stem}_{timestamp}{source_path.suffix}"


    # Move the file.
    #
    # shutil.move()
    #
    # source -----> destination
    shutil.move(str(source_path), str(destination_path))


    # Return the new location so other code knows where it went.
    return destination_path


# ============================================================
# FIND EVERY ZIP FILE
# ============================================================

# glob("*.zip")
#
# Means:
#
# Search the raw_zips folder for every file ending in ".zip"

zip_files = list(RAW_ZIP_DIR.glob("*.zip"))


# ============================================================
# CHECK IF THERE ARE NO ZIP FILES
# ============================================================

if not zip_files:

    # Tell the user.
    print("No ZIP files found in raw_zips.")

    # Save it in the log.
    logging.info("No ZIP files found in raw_zips.")


# ============================================================
# MAIN PROCESSING LOOP
# ============================================================

# Loop through every ZIP file one at a time.

for zip_path in zip_files:

    # Remove ".zip" from the filename.
    #
    # customers.zip
    #
    # becomes
    #
    # customers
    #
    # Final folder:
    #
    # extracted/customers
    output_folder = EXTRACTED_DIR / zip_path.stem

    try:

        # Show progress in the terminal.
        print(f"Processing: {zip_path.name}")

        # Save progress in the log.
        logging.info(f"Processing ZIP file: {zip_path.name}")


        # --------------------------------------------------
        # VALIDATE THE ZIP FILE
        # --------------------------------------------------

        # Start with no bad file.
        #
        # None means:
        #
        # "No corruption has been found yet."
        bad_file = None


        # Open the ZIP in READ MODE.
        #
        # "r" = Read
        #
        # "with" automatically closes the ZIP after this block.
        with zipfile.ZipFile(zip_path, "r") as zip_ref:

            # Check every file inside the ZIP.
            #
            # Returns:
            #
            # None
            #
            # if everything is healthy.
            #
            # Otherwise returns the FIRST corrupted filename.
            bad_file = zip_ref.testzip()


        # --------------------------------------------------
        # ZIP IS NOW CLOSED
        # --------------------------------------------------
        #
        # This is important!
        #
        # We purposely moved this IF statement
        # OUTSIDE the "with" block.
        #
        # Why?
        #
        # Windows locks files while they are open.
        #
        # We cannot move a ZIP while Python still has it open.
        #
        # The "with" block automatically closes the ZIP.
        #
        # NOW it is safe to move it.


        if bad_file:

            print(f"Rejected: {zip_path.name}")

            print(f"Problem file inside ZIP: {bad_file}")

            logging.error(
                f"Rejected {zip_path.name}. Bad file inside ZIP: {bad_file}"
            )

            # Move the bad ZIP into the rejected folder.
            rejected_path = move_file_safe(
                zip_path,
                REJECTED_DIR
            )

            logging.info(
                f"Moved rejected ZIP to: {rejected_path}"
            )

            # Skip extraction.
            #
            # Go immediately to the next ZIP file.
            continue


        # --------------------------------------------------
        # ZIP PASSED VALIDATION
        # --------------------------------------------------

        # Open it AGAIN.
        #
        # Why?
        #
        # The first time was ONLY to validate.
        #
        # Now we reopen it for extraction.
        with zipfile.ZipFile(zip_path, "r") as zip_ref:

            # Create the extraction folder.
            output_folder.mkdir(exist_ok=True)

            # Extract every file.
            zip_ref.extractall(output_folder)


        # --------------------------------------------------
        # ARCHIVE SUCCESSFUL ZIP
        # --------------------------------------------------

        archived_path = move_file_safe(
            zip_path,
            ARCHIVE_DIR
        )


        # Show success.
        print(f"Extracted: {zip_path.name} -> {output_folder}")

        print(f"Archived ZIP -> {archived_path}")


        # Save success to the log.
        logging.info(
            f"Extracted {zip_path.name} to {output_folder}"
        )

        logging.info(
            f"Archived ZIP to {archived_path}"
        )


    # ======================================================
    # ZIP CANNOT EVEN BE OPENED
    # ======================================================

    except zipfile.BadZipFile:

        print(
            f"Rejected: {zip_path.name}. The ZIP file is corrupted."
        )

        logging.error(
            f"Rejected {zip_path.name}. BadZipFile error."
        )

        rejected_path = move_file_safe(
            zip_path,
            REJECTED_DIR
        )

        logging.info(
            f"Moved rejected ZIP to: {rejected_path}"
        )


    # ======================================================
    # ANY OTHER UNEXPECTED ERROR
    # ======================================================

    except Exception as error:

        print(
            f"Failed to process {zip_path.name}: {error}"
        )

        # Save the FULL error and traceback.
        logging.exception(
            f"Unexpected error while processing {zip_path.name}"
        )

        rejected_path = move_file_safe(
            zip_path,
            REJECTED_DIR
        )

        logging.info(
            f"Moved failed ZIP to: {rejected_path}"
        )
