"""Logging helpers for the Substance Painter plugin."""

from __future__ import annotations

import logging
import sys


DEFAULT_BASE_LOGGER_NAME = "axe_usd"
BASE_LOGGER_NAME = DEFAULT_BASE_LOGGER_NAME
_HANDLER_NAME = "axe_usd_stdout"


def derive_base_logger_name(module_name: str) -> str:
    if not module_name:
        return DEFAULT_BASE_LOGGER_NAME
    base = module_name.split(".", 1)[0]
    return base or DEFAULT_BASE_LOGGER_NAME


def _ensure_stdout_handler(base_logger: logging.Logger) -> None:
    for handler in base_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and getattr(
            handler, "stream", None
        ) is sys.stdout:
            return

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(
        logging.Formatter("[AxeUSD] %(levelname)s: %(message)s")
    )
    stream_handler.name = _HANDLER_NAME
    base_logger.addHandler(stream_handler)


def configure_logging(
    module_name: str, level: int = logging.DEBUG
) -> logging.Logger:
    global BASE_LOGGER_NAME
    if BASE_LOGGER_NAME == DEFAULT_BASE_LOGGER_NAME:
        BASE_LOGGER_NAME = derive_base_logger_name(module_name)

    base_logger = logging.getLogger(BASE_LOGGER_NAME)
    _ensure_stdout_handler(base_logger)
    base_logger.setLevel(level)
    base_logger.propagate = False
    return base_logger


def set_base_log_level(level: int) -> None:
    logging.getLogger(BASE_LOGGER_NAME).setLevel(level)


def get_base_logger_name() -> str:
    return BASE_LOGGER_NAME
