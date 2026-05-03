"""Unit tests for services.exports._build_context — pure function.

Verifies number formatting, string assembly, and graceful logo handling.
Does not touch WeasyPrint."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from api.services.branding import Branding
from api.services.exports import _build_context


def _snapshot_dict(**overrides: Any) -> dict[str, Any]:
    base = {
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
            "tenants": [],
            "parking": [],
            "monthly_operating_expenses": "100000",
            "vacancy_allowance_pct": "0.05",
            "cap_rate": "0.10",
        },
        "result_json": {
            "engine_version": "0.1.0",
            "valuation_date": "2026-03-15",
            "tenants_resolved": [],
            "gross_monthly_rent_tenants": "0",
            "gross_monthly_rent_parking": "0",
            "gross_monthly_income": "0",
            "gross_annual_income": "0",
            "annual_operating_expenses": "1200000",
            "opex_per_m2_pm": "0",
            "opex_pct_of_gai": "0",
            "vacancy_allowance_amount": "0",
            "annual_net_income": "-1200000",
            "capitalised_value": "-12000000",
            "market_value": "12500000",
            "warnings": [],
        },
        "market_value": Decimal("12500000"),
        "cap_rate": Decimal("0.10"),
    }
    base.update(overrides)
    return base


def _branding(**overrides: Any) -> Branding:
    base: dict[str, Any] = {
        "firm_name": "Anchor Point Risk",
        "firm_logo_path": None,
        "firm_address_lines": ["1 Example St", "Sandton"],
        "firm_contact_lines": ["+27 11 555 0000"],
    }
    base.update(overrides)
    return Branding(**base)


def test_market_value_is_formatted_with_R_and_thousands_sep() -> None:
    ctx = _build_context(
        _snapshot_dict(), _branding(), generated_at_iso="2026-05-03T12:00:00Z"
    )
    assert ctx["snapshot"]["market_value_formatted"] == "R 12,500,000"


def test_source_manual_renders_human_label() -> None:
    ctx = _build_context(
        _snapshot_dict(source="manual"), _branding(),
        generated_at_iso="2026-05-03T12:00:00Z",
    )
    assert ctx["snapshot"]["source"] == "Manual entry"


def test_source_excel_import_includes_filename() -> None:
    ctx = _build_context(
        _snapshot_dict(source="excel_import", source_file="55 Empire Road.xlsx"),
        _branding(), generated_at_iso="2026-05-03T12:00:00Z",
    )
    assert ctx["snapshot"]["source"] == "Excel import — 55 Empire Road.xlsx"


def test_valuation_date_long_formatted() -> None:
    ctx = _build_context(
        _snapshot_dict(), _branding(), generated_at_iso="2026-05-03T12:00:00Z"
    )
    assert ctx["snapshot"]["valuation_date"] == "15 March 2026"


def test_no_warnings_results_in_empty_list() -> None:
    ctx = _build_context(
        _snapshot_dict(), _branding(), generated_at_iso="2026-05-03T12:00:00Z"
    )
    assert ctx["warnings"] == []


def test_warnings_round_trip() -> None:
    snap = _snapshot_dict()
    snap["result_json"]["warnings"] = [
        {
            "code": "lease_expired",
            "message": "Tenant lease expired",
            "field_path": "tenants[2].lease_expiry_date",
        }
    ]
    ctx = _build_context(snap, _branding(), generated_at_iso="2026-05-03T12:00:00Z")
    assert len(ctx["warnings"]) == 1
    assert ctx["warnings"][0]["code"] == "lease_expired"


def test_branding_logo_None_omitted() -> None:
    ctx = _build_context(
        _snapshot_dict(), _branding(firm_logo_path=None),
        generated_at_iso="2026-05-03T12:00:00Z",
    )
    assert ctx["branding"]["firm_logo_path"] is None
