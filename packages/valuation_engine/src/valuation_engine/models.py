"""Pydantic models for the valuation engine.

All money/rate values are `Decimal`. JSON serialisation emits Decimals as
strings to preserve precision across the API boundary.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BayType = Literal["open", "covered", "shade", "basement", "other"]
Rounding = Literal["nearest_10000", "nearest_1000", "none"]


class _Frozen(BaseModel):
    model_config = ConfigDict(
        frozen=False,  # constructable; we don't enforce immutability inside engine
        extra="forbid",
        ser_json_inf_nan="strings",
    )


class TenantLine(_Frozen):
    description: str
    tenant_name: str | None = None
    rentable_area_m2: Decimal = Field(gt=0)
    rent_per_m2_pm: Decimal = Field(ge=0)
    annual_escalation_pct: Decimal = Field(ge=0)
    next_escalation_date: date | None = None
    lease_period_text: str | None = None
    lease_expiry_date: date | None = None


class ParkingLine(_Frozen):
    bay_type: BayType
    bays: int = Field(ge=0)
    rate_per_bay_pm: Decimal = Field(ge=0)


class ValuationInput(_Frozen):
    valuation_date: date
    tenants: list[TenantLine] = Field(min_length=1)
    parking: list[ParkingLine] = Field(default_factory=list)
    monthly_operating_expenses: Decimal = Field(ge=0)
    vacancy_allowance_pct: Decimal = Field(ge=0, le=1)
    cap_rate: Decimal = Field(gt=0)
    rounding: Rounding = "nearest_10000"

    @field_validator("cap_rate")
    @classmethod
    def _cap_rate_positive(cls, v: Decimal) -> Decimal:
        # Pydantic gt=0 already enforces, kept for explicit intent / future warning thresholds.
        return v


class ResolvedTenant(_Frozen):
    description: str
    rentable_area_m2: Decimal
    effective_rent_per_m2_pm: Decimal
    monthly_rent: Decimal
    escalation_cycles_applied: int


class Warning(_Frozen):
    code: str
    message: str
    field_path: str | None = None


class ValuationResult(_Frozen):
    engine_version: str
    valuation_date: date
    tenants_resolved: list[ResolvedTenant]
    gross_monthly_rent_tenants: Decimal
    gross_monthly_rent_parking: Decimal
    gross_monthly_income: Decimal
    gross_annual_income: Decimal
    annual_operating_expenses: Decimal
    opex_per_m2_pm: Decimal
    opex_pct_of_gai: Decimal
    vacancy_allowance_amount: Decimal
    annual_net_income: Decimal
    capitalised_value: Decimal
    market_value: Decimal
    warnings: list[Warning]
