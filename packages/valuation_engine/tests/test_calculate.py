from datetime import date
from decimal import Decimal

import pytest

from valuation_engine import calculate
from valuation_engine.models import ParkingLine, TenantLine, ValuationInput


def test_four_sight_dev_market_value():
    """Golden values derived from `1. VALUATION EXAMPLES/4 Sight Dev.xlsx`."""
    inputs = ValuationInput(
        valuation_date=date(2011, 7, 28),
        tenants=[
            TenantLine(
                description="Offices",
                rentable_area_m2=Decimal("182"),
                rent_per_m2_pm=Decimal("85"),
                annual_escalation_pct=Decimal("0"),
            )
        ],
        parking=[
            ParkingLine(bay_type="open", bays=2, rate_per_bay_pm=Decimal("200")),
            ParkingLine(bay_type="covered", bays=3, rate_per_bay_pm=Decimal("380")),
            ParkingLine(bay_type="shade", bays=4, rate_per_bay_pm=Decimal("280")),
        ],
        monthly_operating_expenses=Decimal("2910.17"),
        vacancy_allowance_pct=Decimal("0"),
        cap_rate=Decimal("0.11"),
        rounding="nearest_10000",
    )
    result = calculate(inputs)

    # Tenants: 85 * 182 = 15,470 / month
    assert result.gross_monthly_rent_tenants == Decimal("15470")
    # Parking: 2*200 + 3*380 + 4*280 = 400 + 1140 + 1120 = 2,660
    assert result.gross_monthly_rent_parking == Decimal("2660")
    # GMI = 18,130; GAI = 217,560
    assert result.gross_monthly_income == Decimal("18130")
    assert result.gross_annual_income == Decimal("217560")
    # Annual opex = 2910.17 * 12 = 34,922.04
    assert result.annual_operating_expenses == Decimal("34922.04")
    # Vacancy 0
    assert result.vacancy_allowance_amount == Decimal("0")
    # ANI = 217560 - 34922.04 = 182,637.96
    assert result.annual_net_income == Decimal("182637.96")
    # Capitalised = 182637.96 / 0.11 ≈ 1,660,345.0909...
    cap = Decimal("182637.96") / Decimal("0.11")
    assert result.capitalised_value == cap
    # Rounded to nearest 10,000
    assert result.market_value == Decimal("1660000")


def test_engine_version_recorded():
    inputs = ValuationInput(
        valuation_date=date(2026, 1, 1),
        tenants=[TenantLine(
            description="X",
            rentable_area_m2=Decimal("100"),
            rent_per_m2_pm=Decimal("85"),
            annual_escalation_pct=Decimal("0"),
        )],
        monthly_operating_expenses=Decimal("0"),
        vacancy_allowance_pct=Decimal("0"),
        cap_rate=Decimal("0.10"),
    )
    result = calculate(inputs)
    from valuation_engine import __version__
    assert result.engine_version == __version__


def test_rounding_modes():
    base = ValuationInput(
        valuation_date=date(2026, 1, 1),
        tenants=[TenantLine(
            description="X",
            rentable_area_m2=Decimal("100"),
            rent_per_m2_pm=Decimal("85"),
            annual_escalation_pct=Decimal("0"),
        )],
        monthly_operating_expenses=Decimal("0"),
        vacancy_allowance_pct=Decimal("0"),
        cap_rate=Decimal("0.10"),
    )
    cap = (Decimal("85") * Decimal("100") * 12) / Decimal("0.10")  # 1,020,000

    r10k = calculate(base.model_copy(update={"rounding": "nearest_10000"}))
    r1k = calculate(base.model_copy(update={"rounding": "nearest_1000"}))
    none = calculate(base.model_copy(update={"rounding": "none"}))

    assert r10k.market_value == Decimal("1020000")
    assert r1k.market_value == Decimal("1020000")
    assert none.market_value == cap


def test_warnings_propagated_into_result():
    inputs = ValuationInput(
        valuation_date=date(2026, 1, 1),
        tenants=[TenantLine(
            description="X",
            rentable_area_m2=Decimal("100"),
            rent_per_m2_pm=Decimal("85"),
            annual_escalation_pct=Decimal("0"),
        )],
        monthly_operating_expenses=Decimal("0"),
        vacancy_allowance_pct=Decimal("0"),  # triggers vacancy_zero
        cap_rate=Decimal("0.10"),
    )
    result = calculate(inputs)
    assert any(w.code == "vacancy_zero" for w in result.warnings)


def test_cap_rate_zero_rejected_at_input():
    with pytest.raises(Exception):
        ValuationInput(
            valuation_date=date(2026, 1, 1),
            tenants=[TenantLine(
                description="X",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("85"),
                annual_escalation_pct=Decimal("0"),
            )],
            monthly_operating_expenses=Decimal("0"),
            vacancy_allowance_pct=Decimal("0"),
            cap_rate=Decimal("0"),
        )
