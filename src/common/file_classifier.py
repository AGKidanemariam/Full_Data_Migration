"""
File classification utilities.

Responsible for determining what type of file
has arrived in the pipeline.
"""

from pathlib import Path


def is_zip_file(file_path: Path) -> bool:
    """
    Return True if the file has a .zip extension.
    """

    return (
        file_path.is_file()
        and file_path.suffix.lower() == ".zip"
    )