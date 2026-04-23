"""Parameterised golden regression tests across all imported sample sheets."""
from __future__ import annotations

from pathlib import Path

import pytest

from valuation_engine import calculate
from valuation_engine.models import ValuationInput, ValuationResult

GOLDEN = Path(__file__).parent
INPUTS = GOLDEN / "inputs"
EXPECTED = GOLDEN / "expected"


def _pairs() -> list[tuple[Path, Path]]:
    return sorted(
        (p, EXPECTED / p.name)
        for p in INPUTS.glob("*.json")
        if (EXPECTED / p.name).exists()
    )


@pytest.mark.parametrize(
    ("input_path", "expected_path"),
    _pairs(),
    ids=lambda p: p.stem if isinstance(p, Path) else str(p),
)
def test_golden(input_path: Path, expected_path: Path):
    inputs = ValuationInput.model_validate_json(input_path.read_text())
    expected = ValuationResult.model_validate_json(expected_path.read_text())
    actual = calculate(inputs)
    # engine_version is recomputed, ignore for comparison.
    assert actual.model_copy(update={"engine_version": expected.engine_version}) == expected
