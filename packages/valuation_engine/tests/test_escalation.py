from datetime import date
from decimal import Decimal

from valuation_engine.escalation import resolve_rent
from valuation_engine.models import TenantLine


def _t(rent="100", esc="0.08", next_date=None) -> TenantLine:
    return TenantLine(
        description="Office",
        rentable_area_m2=Decimal("100"),
        rent_per_m2_pm=Decimal(rent),
        annual_escalation_pct=Decimal(esc),
        next_escalation_date=next_date,
    )


def test_no_escalation_date_returns_current_rent():
    rent, cycles = resolve_rent(_t(next_date=None), valuation_date=date(2030, 1, 1))
    assert rent == Decimal("100")
    assert cycles == 0


def test_valuation_date_before_next_escalation_returns_current_rent():
    t = _t(next_date=date(2027, 1, 1))
    rent, cycles = resolve_rent(t, valuation_date=date(2026, 6, 1))
    assert rent == Decimal("100")
    assert cycles == 0


def test_one_cycle_when_valuation_date_equals_next_escalation():
    t = _t(rent="100", esc="0.10", next_date=date(2026, 4, 1))
    rent, cycles = resolve_rent(t, valuation_date=date(2026, 4, 1))
    assert cycles == 1
    assert rent == Decimal("100") * (Decimal("1") + Decimal("0.10"))


def test_two_cycles_one_year_after_next_escalation():
    t = _t(rent="100", esc="0.10", next_date=date(2025, 4, 1))
    rent, cycles = resolve_rent(t, valuation_date=date(2026, 4, 1))
    assert cycles == 2
    assert rent == Decimal("100") * (Decimal("1") + Decimal("0.10")) ** 2


def test_zero_escalation_pct_yields_unchanged_rent_with_cycles_counted():
    t = _t(rent="100", esc="0", next_date=date(2025, 1, 1))
    rent, cycles = resolve_rent(t, valuation_date=date(2027, 1, 1))
    # Cycles still increment, but multiplier is 1.
    assert cycles >= 1
    assert rent == Decimal("100")


def test_mid_cycle_rent_is_step_function():
    """Rent does not compound continuously; it's a step function on anniversaries."""
    t = _t(rent="100", esc="0.10", next_date=date(2025, 4, 1))
    on_anniv = resolve_rent(t, valuation_date=date(2025, 4, 1))
    midway = resolve_rent(t, valuation_date=date(2025, 10, 15))
    just_before_next = resolve_rent(t, valuation_date=date(2026, 3, 31))
    assert on_anniv == midway == just_before_next
    assert on_anniv[1] == 1


def test_leap_day_anniversary_rolls_on_mar_1_in_non_leap_year():
    """Feb 28 in a non-leap year is 'before' a Feb 29 anniversary; Mar 1 triggers."""
    t = _t(rent="100", esc="0.10", next_date=date(2024, 2, 29))
    assert resolve_rent(t, date(2025, 2, 28))[1] == 1
    assert resolve_rent(t, date(2025, 3, 1))[1] == 2


def test_multi_cycle_compounding_uses_exponentiation_not_simple_interest():
    """Rent compounds via (1+esc)^cycles, not 1 + esc*cycles."""
    t = _t(rent="100", esc="0.10", next_date=date(2020, 1, 1))
    rent, cycles = resolve_rent(t, valuation_date=date(2024, 1, 1))
    assert cycles == 5
    assert rent == Decimal("100") * (Decimal("1") + Decimal("0.10")) ** 5
    # Sanity: distinct from simple interest.
    assert rent != Decimal("100") * (Decimal("1") + Decimal("0.10") * 5)
