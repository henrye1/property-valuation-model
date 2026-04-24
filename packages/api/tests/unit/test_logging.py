# packages/api/tests/unit/test_logging.py
from __future__ import annotations

import json
import logging

from api.logging import configure_logging


def test_configure_logging_emits_json(caplog, capsys) -> None:
    configure_logging(level="INFO", env="prod")
    log = logging.getLogger("api.test")
    log.info("hello", extra={"request_id": "abc"})

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured, "expected JSON log line on stdout"
    payload = json.loads(captured[-1])
    assert payload["message"] == "hello"
    assert payload["request_id"] == "abc"
    assert payload["level"] == "INFO"


def test_configure_logging_dev_uses_plain_text(capsys) -> None:
    configure_logging(level="INFO", env="dev")
    log = logging.getLogger("api.test")
    log.info("plain")
    out = capsys.readouterr().out
    # Plain dev formatter is not strict JSON
    assert "plain" in out
