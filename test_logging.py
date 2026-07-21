from src.common.logging_utils import get_logger


logger = get_logger(
    logger_name=__name__,
    stage_name="logging_test",
)

logger.info("This is an informational message.")
logger.warning("This is a warning message.")
logger.error("This is an error message.")