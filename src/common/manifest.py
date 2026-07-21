"""
Shared manifest utilities.

The manifest acts as the audit trail for the pipeline.
Every stage records what happened to every file.
"""

import csv
from datetime import datetime
from pathlib import Path

from config.settings import MANIFEST_FILE


# ---------------------------------------------
# Manifest Columns
# ---------------------------------------------

MANIFEST_COLUMNS = [
    "Run_ID",
    "Stage",
    "File_Name",
    "SHA256",
    "Status",
    "Started_At",
    "Finished_At",
    "Records_Read",
    "Records_Written",
    "Records_Rejected",
    "Message",
]


# ---------------------------------------------
# Create Manifest
# ---------------------------------------------

def initialize_manifest() -> None:
    """
    Create the manifest file if it does not already exist.
    """

    if MANIFEST_FILE.exists():
        return

    with open(
        MANIFEST_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow(MANIFEST_COLUMNS)


# ---------------------------------------------
# Record One Event
# ---------------------------------------------

def record_manifest(
    run_id: str,
    stage: str,
    file_name: str,
    sha256: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    records_read: int,
    records_written: int,
    records_rejected: int,
    message: str,
) -> None:
    """
    Append one record to the processing manifest.
    """

    initialize_manifest()

    with open(
        MANIFEST_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                run_id,
                stage,
                file_name,
                sha256,
                status,
                started_at,
                finished_at,
                records_read,
                records_written,
                records_rejected,
                message,
            ]
        )