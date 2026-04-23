"""Per-tenant rent resolution at a given valuation date."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from valuation_engine.models import TenantLine

ONE = Decimal("1")


def resolve_rent(tenant: TenantLine, valuation_date: date) -> tuple[Decimal, int]:
    """Return (effective_rent_per_m2_pm, cycles_applied) at `valuation_date`.

    Rule (per spec §6.4): rent stays at `rent_per_m2_pm` until `next_escalation_date`.
    On or after that date, rent compounds on each *anniversary* of the next-escalation
    date. Anniversaries are calendar-based (not 365.25-day averages), so leap years
    do not shift the cycle count.

    cycles = years_elapsed_since(next_escalation_date, valuation_date) + 1
    """
    nxt = tenant.next_escalation_date
    if nxt is None or valuation_date < nxt:
        return tenant.rent_per_m2_pm, 0

    years_elapsed = valuation_date.year - nxt.year
    if (valuation_date.month, valuation_date.day) < (nxt.month, nxt.day):
        years_elapsed -= 1
    cycles = years_elapsed + 1

    multiplier = (ONE + tenant.annual_escalation_pct) ** cycles
    return tenant.rent_per_m2_pm * multiplier, cycles
