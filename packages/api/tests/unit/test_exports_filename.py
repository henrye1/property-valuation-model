"""Unit tests for _safe_filename — defends Windows/macOS/Linux filesystems."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from api.routers.exports import _safe_filename


def _snap(
    entity: str = "Empire Road Trust",
    property_: str = "55 Empire Road",
    dt: date = date(2026, 3, 15),
) -> SimpleNamespace:
    return SimpleNamespace(
        entity_name=entity, property_name=property_, valuation_date=dt,
    )


def test_simple_filename() -> None:
    name = _safe_filename(_snap(), "pdf")
    assert name == "Empire_Road_Trust_55_Empire_Road_2026-03-15.pdf"


def test_strips_windows_illegal_chars() -> None:
    name = _safe_filename(_snap(entity='B<>:"/\\|?*ad'), "pdf")
    for ch in '<>:"/\\|?*':
        assert ch not in name


def test_collapses_whitespace() -> None:
    name = _safe_filename(_snap(entity="A   B"), "pdf")
    assert "A_B" in name


def test_truncates_to_200_chars() -> None:
    name = _safe_filename(_snap(entity="x" * 500), "pdf")
    assert len(name) <= 204  # 200 + ".pdf"
