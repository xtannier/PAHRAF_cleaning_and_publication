import logging
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

_LOGGING_INITIALIZED = False


def reduce_noisy_loggers() -> None:
    """Reduce the verbosity of noisy loggers."""
    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "asyncio",
        "chardet",
        "charset_normalizer",
        "h11",
        "openai",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def configure_logging(
    level: Optional[int] = None, logdir: Optional[str] = None
) -> None:
    """
    Configure the root logger for the whole application.
    Safe to call multiple times — configuration is applied only once.
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    # Determine log level
    if level is not None:
        log_level = level
        if os.getenv("LOG_LEVEL") is None:
            os.environ["LOG_LEVEL"] = str(level)
    else:
        log_level = int(os.getenv("LOG_LEVEL", str(logging.INFO)))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(name)s] [%(levelname)s] %(message)s")

    if logdir is None:
        # Console mode
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
        stdout_handler.setFormatter(formatter)

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(formatter)

        root_logger.addHandler(stdout_handler)
        root_logger.addHandler(stderr_handler)
    else:
        # File mode
        logdir_path = Path(logdir)
        logdir_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        info_path = logdir_path / f"{timestamp}_info.log"
        error_path = logdir_path / f"{timestamp}_error.log"

        info_handler = logging.FileHandler(info_path, mode="a", encoding="utf-8")
        info_handler.setLevel(logging.DEBUG)
        info_handler.addFilter(lambda r: r.levelno < logging.WARNING)
        info_handler.setFormatter(formatter)

        error_handler = logging.FileHandler(error_path, mode="a", encoding="utf-8")
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(formatter)

        root_logger.addHandler(info_handler)
        root_logger.addHandler(error_handler)

    _LOGGING_INITIALIZED = True
