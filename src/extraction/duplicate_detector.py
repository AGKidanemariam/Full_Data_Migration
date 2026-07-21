"""
Duplicate detection utilities.

Responsible for determining whether a file
has already been processed based on its SHA-256 hash.
"""

import json

from config.settings import HASH_FILE
from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="extract",
)


def load_hashes() -> set[str]:
    """
    Load all processed hashes.

    Returns
    -------
    set[str]
        Previously processed SHA-256 hashes.
    """

    if not HASH_FILE.exists():

        return set()

    with open(
        HASH_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        return set(json.load(file))


def save_hashes(
    hashes: set[str],
) -> None:
    """
    Save processed hashes.
    """

    with open(
        HASH_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            sorted(hashes),
            file,
            indent=4,
        )


def is_duplicate(
    file_hash: str,
) -> bool:
    """
    Return True if the hash already exists.
    """

    hashes = load_hashes()

    duplicate = file_hash in hashes

    if duplicate:

        logger.warning(
            "Duplicate hash detected."
        )

    return duplicate


def register_hash(
    file_hash: str,
) -> None:
    """
    Register a newly processed hash.
    """

    hashes = load_hashes()

    hashes.add(file_hash)

    save_hashes(hashes)

    logger.info(
        "Registered SHA-256 hash."
    )