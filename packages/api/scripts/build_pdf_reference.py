"""One-shot script to generate the reference PDF used by pdf-mark tests.

Run manually after intentional template changes:
    cd packages/api
    env -u VIRTUAL_ENV uv run --no-sync --extra dev python scripts/build_pdf_reference.py
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from api.services.branding import Branding
from api.services.exports import render_snapshot_pdf

REF = Path(__file__).resolve().parents[1] / "tests" / "pdf" / "reference"
REF.mkdir(parents=True, exist_ok=True)


def main() -> None:
    snapshot = {
        "id": "11111111-1111-1111-1111-111111111111",
        "valuation_date": date(2026, 3, 15),
        "engine_version": "0.1.0",
        "source": "manual",
        "source_file": None,
        "created_by_email": "henry@anchorpointrisk.co.za",
        "property_name": "55 Empire Road",
        "property_address": "55 Empire Rd, Sandton, 2196",
        "entity_name": "Empire Road Trust",
        "inputs_json": {
            "valuation_date": "2026-03-15",
            "tenants": [
                {
                    "description": "Acme Co.",
                    "rentable_area_m2": "250",
                    "rent_per_m2_pm": "180",
                    "annual_escalation_pct": "0.08",
                }
            ],
            "parking": [],
            "monthly_operating_expenses": "18000",
            "vacancy_allowance_pct": "0.05",
            "cap_rate": "0.10",
        },
        "result_json": {
            "engine_version": "0.1.0",
            "valuation_date": "2026-03-15",
            "tenants_resolved": [
                {
                    "description": "Acme Co.",
                    "rentable_area_m2": "250",
                    "effective_rent_per_m2_pm": "180",
                    "monthly_rent": "45000",
                    "escalation_cycles_applied": 0,
                }
            ],
            "gross_monthly_rent_tenants": "45000",
            "gross_monthly_rent_parking": "0",
            "gross_monthly_income": "45000",
            "gross_annual_income": "540000",
            "annual_operating_expenses": "216000",
            "opex_per_m2_pm": "72",
            "opex_pct_of_gai": "0.40",
            "vacancy_allowance_amount": "27000",
            "annual_net_income": "297000",
            "capitalised_value": "2970000",
            "market_value": "2970000",
            "warnings": [],
        },
        "market_value": Decimal("2970000"),
        "cap_rate": Decimal("0.10"),
    }
    branding = Branding(
        firm_name="Anchor Point Risk",
        firm_logo_path=None,
        firm_address_lines=["1 Example St", "Sandton"],
        firm_contact_lines=["+27 11 555 0000"],
    )
    pdf = render_snapshot_pdf(snapshot, branding)
    out = REF / "canonical_one_pager.pdf"
    out.write_bytes(pdf)
    print(f"wrote {out} ({len(pdf):,} bytes)")


if __name__ == "__main__":
    main()
