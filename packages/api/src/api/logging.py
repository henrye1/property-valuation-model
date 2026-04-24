"""Structured JSON logging for the API service."""
from __future__ import annotations

import logging
import sys
from typing import Literal

from pythonjsonlogger import jsonlogger


def configure_logging(*, level: str = "INFO", env: Literal["dev", "ci", "prod"] = "prod") -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if env == "dev":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
    else:
        handler.setFormatter(
            jsonlogger.JsonFormatter(  # type: ignore[no-untyped-call]
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
            )
        )
    root.addHandler(handler)
    root.setLevel(level)
