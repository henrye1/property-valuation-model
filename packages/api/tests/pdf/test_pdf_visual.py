"""pdf-mark tests: validity + content + size sanity for the PDF renderer.

Marked `pdf` because they need WeasyPrint + Pango/Cairo apt deps; opt-out
locally with `pytest -m 'not pdf'`."""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.pdf


def test_reference_pdf_is_valid(reference_one_pager: bytes) -> None:
    import pikepdf
    pdf = pikepdf.Pdf.open(io.BytesIO(reference_one_pager))
    assert len(pdf.pages) == 1


def test_reference_pdf_contains_expected_strings(reference_one_pager: bytes) -> None:
    """Every reader-visible string in the canonical fixture must be present."""
    raw = reference_one_pager
    for needle in (
        b"Property Valuation Report",
        b"55 Empire Road",
        b"Empire Road Trust",
        b"Snapshot ID:",
        b"11111111",
        b"Engine version:",
        b"0.1.0",
    ):
        assert needle in raw, f"Missing expected string: {needle!r}"


def test_reference_pdf_size_within_envelope(reference_one_pager: bytes) -> None:
    """Catch 'logo embedded as 5 MB raw bitmap' style regressions."""
    size = len(reference_one_pager)
    assert 5_000 < size < 200_000, f"PDF size {size} outside expected envelope"
