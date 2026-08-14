import sys

from loguru import logger

from app.config import LOGS_DIR, settings

logger.remove()

logger.add(
    sys.stderr,
    level=settings.log_level,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger.add(
    LOGS_DIR / "copiloto_{time:YYYY-MM-DD}.log",
    level=settings.log_level,
    rotation="00:00",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    encoding="utf-8",
)


def get_logger(name: str | None = None):
    return logger
