from pathlib import Path

import pytest

from valuation_engine.excel.parse import parse_workbook


@pytest.fixture
def four_sight(samples_dir: Path) -> Path:
    return samples_dir / "4 Sight Dev.xlsx"


def test_parse_header(four_sight: Path):
    result = parse_workbook(four_sight)
    assert result.building_name == "4 Sight Dev"
