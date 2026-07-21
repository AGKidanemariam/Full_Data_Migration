from pathlib import Path
import os

from dotenv import load_dotenv

# Project Root

BASE_DIR = Path(__file__).resolve().parent.parent

# Load Environment Variables

load_dotenv(BASE_DIR / ".env")

# Main Project Folders

DATA_DIR = BASE_DIR / os.getenv("DATA_FOLDER", "data")

LOG_DIR = BASE_DIR / os.getenv("LOG_FOLDER", "logs")

METADATA_DIR = BASE_DIR / os.getenv("METADATA_FOLDER", "metadata")

# Data Pipeline Folders

RAW_ZIP_DIR = DATA_DIR / os.getenv("RAW_ZIP_FOLDER", "raw_zips")

EXTRACTED_DIR = DATA_DIR / os.getenv("EXTRACTED_FOLDER", "extracted")

ARCHIVE_DIR = DATA_DIR / os.getenv("ARCHIVE_FOLDER", "archive")

NON_ZIP_DIR = DATA_DIR / os.getenv("NON_ZIP_FOLDER", "non_zip")

REJECTED_DIR = DATA_DIR / os.getenv("REJECTED_FOLDER", "rejected")

CORRUPTED_DIR = REJECTED_DIR / os.getenv(
    "CORRUPTED_FOLDER",
    "corrupted",
)

FAILED_PROCESSING_DIR = REJECTED_DIR / os.getenv(
    "FAILED_PROCESSING_FOLDER",
    "failed_processing",
)

STAGED_DIR = DATA_DIR / os.getenv("STAGED_FOLDER", "staged")

PROCESSED_DIR = DATA_DIR / os.getenv("PROCESSED_FOLDER", "processed")

# Metadata Files

MANIFEST_FILE = METADATA_DIR / os.getenv(
    "MANIFEST_FILE",
    "processing_manifest.csv",
)

HASH_FILE = METADATA_DIR / os.getenv(
    "HASH_FILE",
    "file_hashes.json",
)

# Database

DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure Required Directories Exist

DIRECTORIES = [
    DATA_DIR,
    RAW_ZIP_DIR,
    EXTRACTED_DIR,
    ARCHIVE_DIR,
    NON_ZIP_DIR,
    REJECTED_DIR,
    CORRUPTED_DIR,
    FAILED_PROCESSING_DIR,
    STAGED_DIR,
    PROCESSED_DIR,
    LOG_DIR,
    METADATA_DIR,
]

for directory in DIRECTORIES:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )