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
