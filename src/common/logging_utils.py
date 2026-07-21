"""
Shared logging configuration for the data migration pipeline.

"""

import logging
from datetime import datetime
from pathlib import Path

from config.settings import LOG_DIR


def get_logger(
    logger_name: str,
    stage_name: str,
    run_id: str | None = None,
) -> logging.Logger:
    """
    Create and return a logger for one pipeline stage.

    Parameters
    ----------
    logger_name:
        Usually the module name passed through __name__.

    stage_name:
        A readable pipeline stage such as "extract" or "inspect".

    run_id:
        Optional identifier shared by all stages in one pipeline run.

    Returns
    -------
    logging.Logger
        A configured logger that writes to both the terminal and a log file.
    """

    resolved_run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    log_file: Path = LOG_DIR / f"{stage_name}_{resolved_run_id}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Prevent the same message from being written multiple times if
    # get_logger() is called repeatedly for the same logger.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(
        "Logger initialized | stage=%s | run_id=%s | log_file=%s",
        stage_name,
        resolved_run_id,
        log_file,
    )

    return logger
exit
