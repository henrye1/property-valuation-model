"""Soft data-quality warning detectors. Pure functions over ValuationInput."""
from __future__ import annotations

from decimal import Decimal

from valuation_engine.models import ValuationInput, Warning

OPEX_LOW_PCT = Decimal("0.05")
OPEX_HIGH_PCT = Decimal("0.60")
CAP_RATE_LOW = Decimal("0.06")
CAP_RATE_HIGH = Decimal("0.20")
RENT_LOW = Decimal("20")
RENT_HIGH = Decimal("1000")


def detect_warnings(inputs: ValuationInput) -> list[Warning]:
    warnings: list[Warning] = []

    # Per-tenant warnings
    for i, t in enumerate(inputs.tenants):
        path = f"tenants[{i}]"
        if t.lease_expiry_date is not None and t.lease_expiry_date < inputs.valuation_date:
            warnings.append(
                Warning(
                    code="lease_expired",
                    message=(
                        f"Lease expired on {t.lease_expiry_date.isoformat()} "
                        "(before valuation date)."
                    ),
                    field_path=f"{path}.lease_expiry_date",
                )
            )
        if t.annual_escalation_pct > 0 and t.next_escalation_date is None:
            warnings.append(
                Warning(
                    code="escalation_missing",
                    message=(
                        "Escalation rate is set but no next escalation date — "
                        "escalation will not be applied."
                    ),
                    field_path=f"{path}.next_escalation_date",
                )
            )
        if t.rent_per_m2_pm < RENT_LOW or t.rent_per_m2_pm > RENT_HIGH:
            warnings.append(
                Warning(
                    code="rent_unusual",
                    message=(
                        f"Rent {t.rent_per_m2_pm} R/m²/pm is outside "
                        f"[{RENT_LOW}, {RENT_HIGH}]."
                    ),
                    field_path=f"{path}.rent_per_m2_pm",
                )
            )

    # Vacancy
    if inputs.vacancy_allowance_pct == 0:
        warnings.append(
            Warning(
                code="vacancy_zero",
                message="Vacancy allowance is 0% — no vacancy buffer applied.",
                field_path="vacancy_allowance_pct",
            )
        )

    # Cap rate band
    if inputs.cap_rate < CAP_RATE_LOW or inputs.cap_rate > CAP_RATE_HIGH:
        warnings.append(
            Warning(
                code="cap_rate_unusual",
                message=(
                    f"Capitalisation rate {inputs.cap_rate} outside "
                    f"[{CAP_RATE_LOW}, {CAP_RATE_HIGH}]."
                ),
                field_path="cap_rate",
            )
        )

    # Opex (uses GAI from rent roll only — parking excluded for the band check)
    annual_opex = inputs.monthly_operating_expenses * 12
    if annual_opex == 0:
        warnings.append(
            Warning(
                code="opex_zero",
                message="Operating expenses are 0 — verify this is correct.",
                field_path="monthly_operating_expenses",
            )
        )
    else:
        gai_tenants = sum(
            (t.rent_per_m2_pm * t.rentable_area_m2 for t in inputs.tenants),
            start=Decimal("0"),
        ) * 12
        if gai_tenants > 0:
            opex_pct = annual_opex / gai_tenants
            if opex_pct < OPEX_LOW_PCT or opex_pct > OPEX_HIGH_PCT:
                warnings.append(
                    Warning(
                        code="opex_unusual_pct",
                        message=(
                            f"Operating expenses are {opex_pct:.2%} of GAI "
                            f"(band: {OPEX_LOW_PCT:.0%}–{OPEX_HIGH_PCT:.0%})."
                        ),
                        field_path="monthly_operating_expenses",
                    )
                )

    return warnings
