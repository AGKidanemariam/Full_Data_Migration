"""
Shared hashing utilities.

Provides reusable functions for generating file hashes.
"""

import hashlib
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate the SHA-256 hash of a file.

    Parameters
    ----------
    file_path:
        The file to hash.

    Returns
    -------
    str
        The hexadecimal SHA-256 digest.
    """

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while chunk := file.read(8192):

            sha256.update(chunk)

    return sha256.hexdigest()
