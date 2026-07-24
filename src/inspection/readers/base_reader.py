"""
Base reader contract.

Provides the common profiling workflow for every
reader in the inspection stage.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime

from src.common.logging_utils import get_logger
from src.common.models.data_profile import DataProfile


class BaseReader(ABC):
    """
    Abstract base class for every reader.
    """

    def __init__(self) -> None:

        self.logger = get_logger(
            logger_name=self.__class__.__name__,
            stage_name="inspection",
        )

    @property
    @abstractmethod
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:
        """
        Extensions handled by this reader.
        """

        raise NotImplementedError

    def supports(
        self,
        file_path: Path,
    ) -> bool:

        return (
            file_path.suffix.lower()
            in self.supported_extensions
        )

    def profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Execute the complete profiling workflow.

        Child classes should never override this.
        """

        start_time = datetime.now()

        self.logger.info(
            "Starting profile for %s",
            file_path.name,
        )

        try:

            profile = self._build_profile(
                file_path,
            )

            elapsed = (
                datetime.now() - start_time
            ).total_seconds()

            self.logger.info(
                "Finished profiling %s in %.3f seconds",
                file_path.name,
                elapsed,
            )

            return profile

        except Exception as error:

            self.logger.exception(
                "Profiling failed for %s",
                file_path.name,
            )

            return DataProfile(
                file_path=file_path,
                file_name=file_path.name,
                extension=file_path.suffix.lower(),
                file_size_bytes=file_path.stat().st_size,
                profile_type="Unknown",
                inspection_status="Failed",
                inspection_message=str(error),
            )

    @abstractmethod
    def _build_profile(
        self,
        file_path: Path,
    ) -> DataProfile:
        """
        Build a profile for one file.

        Only this method should be implemented
        by child readers.
        """

        raise NotImplementedError