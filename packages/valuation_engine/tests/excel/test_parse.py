from decimal import Decimal
from pathlib import Path

import pytest

from valuation_engine.excel.parse import parse_workbook


@pytest.fixture
def four_sight(samples_dir: Path) -> Path:
    return samples_dir / "4 Sight Dev.xlsx"


def test_parse_header(four_sight: Path):
    result = parse_workbook(four_sight)
    assert result.building_name == "4 Sight Dev"


def test_parse_tenants_four_sight(four_sight):
    result = parse_workbook(four_sight)
    assert result.inputs is not None
    assert len(result.inputs.tenants) == 1
    t = result.inputs.tenants[0]
    assert t.description == "Offices"
    assert t.rentable_area_m2 == Decimal("182")
    assert t.rent_per_m2_pm == Decimal("85")


def test_parse_parking_four_sight(four_sight):
    result = parse_workbook(four_sight)
    assert result.inputs is not None
    parking = result.inputs.parking
    assert len(parking) == 3
    bay_types = {p.bay_type for p in parking}
    assert bay_types == {"open", "covered", "shade"}
    open_bay = next(p for p in parking if p.bay_type == "open")
    assert open_bay.bays == 2
    assert open_bay.rate_per_bay_pm == Decimal("200")


def test_parse_assumptions_four_sight(four_sight):
    result = parse_workbook(four_sight)
    assert result.inputs is not None
    assert result.inputs.cap_rate == Decimal("0.11")
    assert result.inputs.vacancy_allowance_pct == Decimal("0")
    # Monthly opex from `=34922/12` in the sheet → 2,910.166...
    assert result.inputs.monthly_operating_expenses > Decimal("2900")
    assert result.inputs.monthly_operating_expenses < Decimal("2920")


def test_parse_sheet_market_value(four_sight):
    result = parse_workbook(four_sight)
    assert result.sheet_market_value is not None
    assert result.sheet_market_value == Decimal("1660000")
