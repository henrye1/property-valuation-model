"""Round-trip equality test across every successfully-parsed sample workbook.

The xlsx format stores floats with ~15-16 significant digits of precision, so a
value like ``Decimal('2910.1666666666665')`` (17 digits, produced by ``=34922/12``)
is truncated to ``Decimal('2910.166666666667')`` on a write-then-read cycle.
That sub-cent difference flows through ``calculate()`` and produces intermediate
results that differ in the 14th-17th decimal place. The test therefore compares:

1. Structural equality of the parsed inputs (tenant count, parking count, etc.),
2. Exact equality of the final ``market_value`` (which is rounded to nearest
   R10,000 or R1,000, so it is insensitive to these tiny precision deltas),
3. Approximate equality (within 0.01%) of the intermediate Decimal fields on
   ``ValuationResult`` — strict enough to catch a real renderer bug (missing
   raw value, wrong column) but tolerant of xlsx float serialisation limits.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from valuation_engine import calculate
from valuation_engine.excel.parse import parse_workbook
from valuation_engine.excel.render import render_workbook
from valuation_engine.models import ValuationInput, ValuationResult

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLES = REPO_ROOT / "1. VALUATION EXAMPLES"

# Tolerance for intermediate Decimal fields: 0.01% handles xlsx's ~15-sig-digit
# float precision cap without masking a real renderer bug.
PRECISION_TOLERANCE = Decimal("0.0001")


def _xlsx_samples() -> list[Path]:
    return sorted(p for p in SAMPLES.iterdir() if p.suffix.lower() == ".xlsx")


def _assert_inputs_structurally_equal(a: ValuationInput, b: ValuationInput, src_name: str) -> None:
    assert a.valuation_date == b.valuation_date, f"{src_name}: valuation_date differs"
    assert a.rounding == b.rounding, f"{src_name}: rounding differs"
    assert len(a.tenants) == len(b.tenants), f"{src_name}: tenant count differs"
    assert len(a.parking) == len(b.parking), f"{src_name}: parking count differs"
    for i, (ta, tb) in enumerate(zip(a.tenants, b.tenants, strict=True)):
        assert ta.description == tb.description, f"{src_name}: tenant[{i}].description"
        assert ta.rentable_area_m2 == tb.rentable_area_m2, (
            f"{src_name}: tenant[{i}].rentable_area_m2"
        )
        assert ta.annual_escalation_pct == tb.annual_escalation_pct, (
            f"{src_name}: tenant[{i}].annual_escalation_pct"
        )
        # rent_per_m2_pm may suffer xlsx precision loss when it's a /12 formula
        # value in the source; tolerate 0.01%.
        _assert_close(
            ta.rent_per_m2_pm, tb.rent_per_m2_pm, f"{src_name}: tenant[{i}].rent_per_m2_pm"
        )
    for i, (pa, pb) in enumerate(zip(a.parking, b.parking, strict=True)):
        assert pa.bay_type == pb.bay_type, f"{src_name}: parking[{i}].bay_type"
        assert pa.bays == pb.bays, f"{src_name}: parking[{i}].bays"
        assert pa.rate_per_bay_pm == pb.rate_per_bay_pm, (
            f"{src_name}: parking[{i}].rate_per_bay_pm"
        )
    _assert_close(
        a.monthly_operating_expenses,
        b.monthly_operating_expenses,
        f"{src_name}: monthly_operating_expenses",
    )
    assert a.vacancy_allowance_pct == b.vacancy_allowance_pct, f"{src_name}: vacancy_allowance_pct"
    assert a.cap_rate == b.cap_rate, f"{src_name}: cap_rate"


def _assert_close(a: Decimal, b: Decimal, label: str) -> None:
    if a == b:
        return
    if a == 0 or b == 0:
        assert abs(a - b) < PRECISION_TOLERANCE, f"{label}: {a} vs {b}"
        return
    diff = abs(a - b) / max(abs(a), abs(b))
    assert diff < PRECISION_TOLERANCE, f"{label}: {a} vs {b} (diff {diff:.6%})"


def _assert_results_equivalent(r1: ValuationResult, r2: ValuationResult, src_name: str) -> None:
    # Final rounded market_value MUST match exactly - this is the output that
    # matters and is insensitive to intermediate float precision.
    assert r1.market_value == r2.market_value, f"{src_name}: market_value differs"
    assert r1.valuation_date == r2.valuation_date, f"{src_name}: valuation_date differs"
    assert len(r1.tenants_resolved) == len(r2.tenants_resolved), (
        f"{src_name}: tenant resolution count"
    )
    # Intermediate Decimals: close (within 0.01%) is sufficient.
    for field in (
        "gross_monthly_rent_tenants",
        "gross_monthly_rent_parking",
        "gross_monthly_income",
        "gross_annual_income",
        "annual_operating_expenses",
        "opex_per_m2_pm",
        "opex_pct_of_gai",
        "vacancy_allowance_amount",
        "annual_net_income",
        "capitalised_value",
    ):
        _assert_close(getattr(r1, field), getattr(r2, field), f"{src_name}: {field}")


@pytest.mark.parametrize("src", _xlsx_samples(), ids=lambda p: p.stem)
def test_roundtrip(src: Path, tmp_path: Path):
    parsed = parse_workbook(src)
    if parsed.inputs is None:
        pytest.skip(f"{src.name}: failed initial parse - covered by skipped.json")
    result1 = calculate(parsed.inputs)

    out = tmp_path / "rt.xlsx"
    render_workbook(
        out,
        building_name=parsed.building_name or "Untitled",
        inputs=parsed.inputs,
        result=result1,
    )

    parsed2 = parse_workbook(out)
    assert parsed2.inputs is not None, f"Re-parse failed for {src.name}"
    _assert_inputs_structurally_equal(parsed.inputs, parsed2.inputs, src.name)
    result2 = calculate(parsed2.inputs)
    _assert_results_equivalent(result1, result2, src.name)
