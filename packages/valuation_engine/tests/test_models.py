from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from valuation_engine.models import (
    ParkingLine,
    ResolvedTenant,
    TenantLine,
    ValuationInput,
    ValuationResult,
    Warning,
)


def test_tenant_line_minimum_fields():
    t = TenantLine(
        description="Offices",
        rentable_area_m2=Decimal("100"),
        rent_per_m2_pm=Decimal("85"),
        annual_escalation_pct=Decimal("0.08"),
    )
    assert t.tenant_name is None
    assert t.next_escalation_date is None


def test_parking_line_bay_type_enum():
    p = ParkingLine(bay_type="open", bays=2, rate_per_bay_pm=Decimal("200"))
    assert p.bay_type == "open"
    with pytest.raises(ValidationError):
        ParkingLine(bay_type="rooftop", bays=1, rate_per_bay_pm=Decimal("0"))


def test_valuation_input_requires_tenants():
    with pytest.raises(ValidationError):
        ValuationInput(
            valuation_date=date(2026, 1, 1),
            tenants=[],
            monthly_operating_expenses=Decimal("0"),
            vacancy_allowance_pct=Decimal("0"),
            cap_rate=Decimal("0.10"),
        )


def test_valuation_input_default_rounding():
    v = ValuationInput(
        valuation_date=date(2026, 1, 1),
        tenants=[
            TenantLine(
                description="Office",
                rentable_area_m2=Decimal("100"),
                rent_per_m2_pm=Decimal("85"),
                annual_escalation_pct=Decimal("0"),
            )
        ],
        monthly_operating_expenses=Decimal("0"),
        vacancy_allowance_pct=Decimal("0"),
        cap_rate=Decimal("0.10"),
    )
    assert v.rounding == "nearest_10000"


def test_warning_construction():
    w = Warning(code="vacancy_zero", message="vacancy is 0", field_path=None)
    assert w.code == "vacancy_zero"


def test_resolved_tenant_carries_cycles():
    rt = ResolvedTenant(
        description="Office",
        rentable_area_m2=Decimal("100"),
        effective_rent_per_m2_pm=Decimal("100"),
        monthly_rent=Decimal("10000"),
        escalation_cycles_applied=2,
    )
    assert rt.escalation_cycles_applied == 2


def test_valuation_result_round_trip_json():
    r = ValuationResult(
        engine_version="0.1.0",
        valuation_date=date(2026, 1, 1),
        tenants_resolved=[],
        gross_monthly_rent_tenants=Decimal("0"),
        gross_monthly_rent_parking=Decimal("0"),
        gross_monthly_income=Decimal("0"),
        gross_annual_income=Decimal("0"),
        annual_operating_expenses=Decimal("0"),
        opex_per_m2_pm=Decimal("0"),
        opex_pct_of_gai=Decimal("0"),
        vacancy_allowance_amount=Decimal("0"),
        annual_net_income=Decimal("0"),
        capitalised_value=Decimal("0"),
        market_value=Decimal("0"),
        warnings=[],
    )
    payload = r.model_dump_json()
    again = ValuationResult.model_validate_json(payload)
    assert again == r


def test_valuation_result_decimal_serialises_as_string():
    """Pin the wire format: Decimals must serialise as JSON strings, not numbers.

    Downstream consumers (FastAPI / React zod schemas) rely on this to preserve
    precision across the wire. A future Pydantic version that flips the default
    to numbers would silently break the web client; this test catches it.
    """
    r = ValuationResult(
        engine_version="0.1.0",
        valuation_date=date(2026, 1, 1),
        tenants_resolved=[],
        gross_monthly_rent_tenants=Decimal("0"),
        gross_monthly_rent_parking=Decimal("0"),
        gross_monthly_income=Decimal("0"),
        gross_annual_income=Decimal("0"),
        annual_operating_expenses=Decimal("0"),
        opex_per_m2_pm=Decimal("0"),
        opex_pct_of_gai=Decimal("0"),
        vacancy_allowance_amount=Decimal("0"),
        annual_net_income=Decimal("0"),
        capitalised_value=Decimal("0"),
        market_value=Decimal("1050000.50"),
        warnings=[],
    )
    payload = r.model_dump_json()
    assert '"market_value":"1050000.50"' in payload


def test_tenant_line_rejects_zero_area():
    with pytest.raises(ValidationError):
        TenantLine(
            description="Offices",
            rentable_area_m2=Decimal("0"),
            rent_per_m2_pm=Decimal("85"),
            annual_escalation_pct=Decimal("0"),
        )


def test_valuation_input_rejects_zero_cap_rate():
    with pytest.raises(ValidationError):
        ValuationInput(
            valuation_date=date(2026, 1, 1),
            tenants=[
                TenantLine(
                    description="Office",
                    rentable_area_m2=Decimal("100"),
                    rent_per_m2_pm=Decimal("85"),
                    annual_escalation_pct=Decimal("0"),
                )
            ],
            monthly_operating_expenses=Decimal("0"),
            vacancy_allowance_pct=Decimal("0"),
            cap_rate=Decimal("0"),
        )


def test_valuation_input_rejects_vacancy_above_one():
    with pytest.raises(ValidationError):
        ValuationInput(
            valuation_date=date(2026, 1, 1),
            tenants=[
                TenantLine(
                    description="Office",
                    rentable_area_m2=Decimal("100"),
                    rent_per_m2_pm=Decimal("85"),
                    annual_escalation_pct=Decimal("0"),
                )
            ],
            monthly_operating_expenses=Decimal("0"),
            vacancy_allowance_pct=Decimal("1.5"),
            cap_rate=Decimal("0.10"),
        )
