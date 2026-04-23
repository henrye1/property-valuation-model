"""Parameterised golden regression tests across all imported sample sheets."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from valuation_engine import calculate
from valuation_engine.models import ValuationInput, ValuationResult

GOLDEN = Path(__file__).parent
INPUTS = GOLDEN / "inputs"
EXPECTED = GOLDEN / "expected"

EXPECTED_SKIP_COUNT = 7  # 1 .xls + 4 missing cap_rate + 2 recompute_mismatch (see skipped.json)


def _pairs() -> list[tuple[Path, Path]]:
    inputs = {p.name for p in INPUTS.glob("*.json")}
    expected = {p.name for p in EXPECTED.glob("*.json")}
    missing_expected = inputs - expected
    missing_inputs = expected - inputs
    if missing_expected or missing_inputs:
        raise RuntimeError(
            f"Orphaned fixtures — missing expected: {sorted(missing_expected)}; "
            f"missing inputs: {sorted(missing_inputs)}"
        )
    return sorted((INPUTS / name, EXPECTED / name) for name in inputs)


@pytest.mark.parametrize(
    ("input_path", "expected_path"),
    _pairs(),
    ids=lambda p: p.stem if isinstance(p, Path) else str(p),
)
def test_golden(input_path: Path, expected_path: Path):
    inputs = ValuationInput.model_validate_json(input_path.read_bytes())
    expected = ValuationResult.model_validate_json(expected_path.read_bytes())
    actual = calculate(inputs)
    # engine_version is recomputed, ignore for comparison.
    assert actual.model_copy(update={"engine_version": expected.engine_version}) == expected


def test_skip_count_unchanged():
    """Locks the size of the golden corpus.

    If a parser improvement rescues a previously-skipped workbook, this test
    fails — forcing a conscious decision to regenerate fixtures and bump
    EXPECTED_SKIP_COUNT (or restore the file). Likewise if a regression
    starts dropping previously-accepted workbooks.
    """
    skipped = json.loads((GOLDEN / "skipped.json").read_bytes())
    assert len(skipped) == EXPECTED_SKIP_COUNT, (
        f"Skip count changed from {EXPECTED_SKIP_COUNT} to {len(skipped)}. "
        "If this is intentional, regenerate fixtures with `python scripts/generate_golden.py` "
        "and update EXPECTED_SKIP_COUNT."
    )
