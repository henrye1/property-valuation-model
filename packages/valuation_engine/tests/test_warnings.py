from datetime import date
from decimal import Decimal

from valuation_engine.models import ParkingLine, TenantLine, ValuationInput
from valuation_engine.warnings import detect_warnings


def _input(**overrides) -> ValuationInput:
    base = dict(
        valuation_date=date(2026, 4, 1),
        tenants=[
            TenantLine(
                description="Office",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("85"),
                annual_escalation_pct=Decimal("0"),
            )
        ],
        parking=[],
        monthly_operating_expenses=Decimal("1000"),
        vacancy_allowance_pct=Decimal("0.05"),
        cap_rate=Decimal("0.115"),
    )
    base.update(overrides)
    return ValuationInput(**base)


def _codes(warnings) -> set[str]:
    return {w.code for w in warnings}


def test_clean_input_yields_no_warnings():
    inputs = _input()
    # GAI = 85*100*12 = 102000; opex annual = 12000; opex_pct = 11.76% (within band)
    assert _codes(detect_warnings(inputs)) == set()


def test_lease_expired_warning():
    inputs = _input(
        tenants=[
            TenantLine(
                description="Office",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("85"),
                annual_escalation_pct=Decimal("0"),
                lease_expiry_date=date(2025, 1, 1),
            )
        ]
    )
    assert "lease_expired" in _codes(detect_warnings(inputs))


def test_escalation_missing_warning():
    inputs = _input(
        tenants=[
            TenantLine(
                description="Office",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("85"),
                annual_escalation_pct=Decimal("0.08"),
                next_escalation_date=None,
            )
        ]
    )
    assert "escalation_missing" in _codes(detect_warnings(inputs))


def test_vacancy_zero_warning():
    inputs = _input(vacancy_allowance_pct=Decimal("0"))
    assert "vacancy_zero" in _codes(detect_warnings(inputs))


def test_opex_zero_warning():
    inputs = _input(monthly_operating_expenses=Decimal("0"))
    assert "opex_zero" in _codes(detect_warnings(inputs))


def test_opex_unusual_pct_warning_high():
    # GAI = 102_000. Set opex annual to 80_000 -> 78% of GAI.
    inputs = _input(monthly_operating_expenses=Decimal("6666.67"))
    assert "opex_unusual_pct" in _codes(detect_warnings(inputs))


def test_cap_rate_unusual_warning():
    inputs = _input(cap_rate=Decimal("0.04"))
    assert "cap_rate_unusual" in _codes(detect_warnings(inputs))


def test_rent_unusual_warning():
    inputs = _input(
        tenants=[
            TenantLine(
                description="Office",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("5"),
                annual_escalation_pct=Decimal("0"),
            )
        ]
    )
    assert "rent_unusual" in _codes(detect_warnings(inputs))


def test_parking_does_not_trigger_rent_unusual():
    inputs = _input(
        parking=[ParkingLine(bay_type="open", bays=2, rate_per_bay_pm=Decimal("200"))]
    )
    # Parking rates are not subject to the rent_unusual band.
    assert "rent_unusual" not in _codes(detect_warnings(inputs))


def test_opex_unusual_pct_warning_low():
    # GAI = 102_000; opex annual = 4000 -> 3.92% (< 5%)
    inputs = _input(monthly_operating_expenses=Decimal("333.33"))
    assert "opex_unusual_pct" in _codes(detect_warnings(inputs))


def test_cap_rate_unusual_warning_high():
    inputs = _input(cap_rate=Decimal("0.25"))
    assert "cap_rate_unusual" in _codes(detect_warnings(inputs))


def test_rent_unusual_warning_high():
    inputs = _input(
        tenants=[
            TenantLine(
                description="Penthouse",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("1500"),
                annual_escalation_pct=Decimal("0"),
            )
        ]
    )
    assert "rent_unusual" in _codes(detect_warnings(inputs))


def test_opex_pct_denominator_excludes_parking():
    """Opex band check uses tenant GAI only — adding parking does not move opex_pct."""
    # Tenant GAI = 85*100*12 = 102_000; annual opex = 80_000 -> 78% (above band).
    # If the denominator wrongly included parking (100 * 500 * 12 = 600_000),
    # opex_pct would drop to ~11.4% (inside band) and the warning would NOT fire.
    inputs = _input(
        monthly_operating_expenses=Decimal("6666.67"),
        parking=[ParkingLine(bay_type="open", bays=100, rate_per_bay_pm=Decimal("500"))],
    )
    assert "opex_unusual_pct" in _codes(detect_warnings(inputs))
