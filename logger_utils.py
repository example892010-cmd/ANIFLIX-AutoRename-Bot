import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger():
    logger = logging.getLogger("aniflix_autorename")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional local log file. Set LOG_TO_FILE=false to disable it.
    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        log_dir = Path(os.getenv("DATA_DIR", "data"))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "bot.log",
                maxBytes=1_000_000,
                backupCount=2,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            logger.warning("File logging unavailable; using console logging only.")

    return logger
