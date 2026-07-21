"""
Shared file utility functions.

These functions are reused across multiple stages
of the data migration pipeline.
"""

from pathlib import Path
import shutil
from datetime import datetime


# ---------------------------------------------------
# Ensure Directory Exists
# ---------------------------------------------------

def ensure_directory_exists(directory: Path) -> None:
    """
    Create a directory if it does not already exist.
    """

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ---------------------------------------------------
# Generate Unique Filename
# ---------------------------------------------------

def generate_unique_filename(file_path: Path) -> Path:
    """
    Prevent overwriting an existing file.

    Example

    report.csv

    becomes

    report_20260720_153001.csv
    """

    if not file_path.exists():
        return file_path

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return file_path.with_name(
        f"{file_path.stem}_{timestamp}{file_path.suffix}"
    )


# ---------------------------------------------------
# Move File Safely
# ---------------------------------------------------

def move_file_safe(
    source: Path,
    destination_directory: Path,
) -> Path:
    """
    Move a file without overwriting an existing one.
    """

    ensure_directory_exists(destination_directory)

    destination = destination_directory / source.name

    destination = generate_unique_filename(destination)

    shutil.move(
        str(source),
        str(destination),
    )

    return destination


# ---------------------------------------------------
# Delete File
# ---------------------------------------------------

def delete_file(file_path: Path) -> None:
    """
    Delete a file if it exists.
    """

    if file_path.exists():
        file_path.unlink()