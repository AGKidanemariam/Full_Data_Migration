"""
File inspection dispatcher.

Delegates profiling to the appropriate reader.
"""

from pathlib import Path

from src.common.logging_utils import get_logger
from src.common.models.data_profile import DataProfile

from src.inspection.readers.registry import (
    ReaderRegistry,
)


logger = get_logger(
    logger_name=__name__,
    stage_name="inspection",
)


_registry = ReaderRegistry()


def inspect_file(
    file_path: Path,
) -> DataProfile:
    """
    Profile one file using the appropriate reader.

    Parameters
    ----------
    file_path:
        File to inspect.

    Returns
    -------
    DataProfile
    """

    reader = _registry.get_reader(
        file_path,
    )

    if reader is None:

        logger.warning(
            "No reader found for %s",
            file_path.name,
        )

        return DataProfile(
            file_path=file_path,
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            profile_type="UNKNOWN",
            inspection_status="Unsupported",
            inspection_message=(
                "No registered reader "
                "supports this file."
            ),
        )

    logger.info(
        "Using %s",
        reader.__class__.__name__,
    )

    return reader.profile(
        file_path,
    )