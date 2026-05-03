"""pdf-mark-only fixtures and shared helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

REF_DIR = Path(__file__).resolve().parent / "reference"


@pytest.fixture(scope="session")
def reference_one_pager() -> bytes:
    p = REF_DIR / "canonical_one_pager.pdf"
    if not p.exists():
        pytest.skip(
            "Reference PDF not generated. Run "
            "'python scripts/build_pdf_reference.py' on a host with "
            "WeasyPrint native libs (or wait for CI to generate it)."
        )
    return p.read_bytes()
