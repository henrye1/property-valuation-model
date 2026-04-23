"""Core valuation calculation. Pure function over ValuationInput."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from valuation_engine._version import __version__
from valuation_engine.escalation import resolve_rent
from valuation_engine.models import (
    ResolvedTenant,
    ValuationInput,
    ValuationResult,
)
from valuation_engine.warnings import detect_warnings

ZERO = Decimal("0")
TWELVE = Decimal("12")
ROUND_INCREMENT = {
    "nearest_10000": Decimal("10000"),
    "nearest_1000": Decimal("1000"),
    "none": Decimal("0"),
}


def calculate(inputs: ValuationInput) -> ValuationResult:
    # Resolve per-tenant rents at valuation date.
    resolved: list[ResolvedTenant] = []
    gross_tenant_rent = ZERO
    total_area = ZERO
    for t in inputs.tenants:
        eff, cycles = resolve_rent(t, inputs.valuation_date)
        monthly = eff * t.rentable_area_m2
        resolved.append(
            ResolvedTenant(
                description=t.description,
                rentable_area_m2=t.rentable_area_m2,
                effective_rent_per_m2_pm=eff,
                monthly_rent=monthly,
                escalation_cycles_applied=cycles,
            )
        )
        gross_tenant_rent += monthly
        total_area += t.rentable_area_m2

    # Parking.
    gross_parking_rent = sum(
        (Decimal(p.bays) * p.rate_per_bay_pm for p in inputs.parking),
        start=ZERO,
    )

    # Income aggregation.
    gross_monthly_income = gross_tenant_rent + gross_parking_rent
    gross_annual_income = gross_monthly_income * TWELVE

    # Operating expenses.
    annual_opex = inputs.monthly_operating_expenses * TWELVE
    opex_per_m2_pm = (
        inputs.monthly_operating_expenses / total_area if total_area > 0 else ZERO
    )
    opex_pct_of_gai = annual_opex / gross_annual_income if gross_annual_income > 0 else ZERO

    # Vacancy is a deduction (negative effect on ANI).
    vacancy_amount = gross_annual_income * inputs.vacancy_allowance_pct
    annual_net_income = gross_annual_income - annual_opex - vacancy_amount

    # Capitalisation.
    capitalised = annual_net_income / inputs.cap_rate
    market_value = _round_to_increment(capitalised, ROUND_INCREMENT[inputs.rounding])

    return ValuationResult(
        engine_version=__version__,
        valuation_date=inputs.valuation_date,
        tenants_resolved=resolved,
        gross_monthly_rent_tenants=gross_tenant_rent,
        gross_monthly_rent_parking=gross_parking_rent,
        gross_monthly_income=gross_monthly_income,
        gross_annual_income=gross_annual_income,
        annual_operating_expenses=annual_opex,
        opex_per_m2_pm=opex_per_m2_pm,
        opex_pct_of_gai=opex_pct_of_gai,
        vacancy_allowance_amount=vacancy_amount,
        annual_net_income=annual_net_income,
        capitalised_value=capitalised,
        market_value=market_value,
        warnings=detect_warnings(inputs),
    )


def _round_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    if increment == ZERO:
        return value
    return (value / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * increment
