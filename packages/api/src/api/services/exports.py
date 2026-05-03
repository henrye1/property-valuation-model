"""PDF rendering for /snapshots/{id}/export.pdf.

Pure context-builder + WeasyPrint plumbing. Number formatting happens here
(not in the template) so unit tests don't need WeasyPrint installed.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api.services.branding import Branding

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "exports"

_jenv = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _fmt_money(value: Any) -> str:
    """Format as 'R 12,500,000.00' (R prefix, thousands sep, two decimals)."""
    if value is None:
        return ""
    d = Decimal(str(value))
    # Strip trailing .00 for whole numbers; otherwise show two decimals.
    if d == d.to_integral_value():
        return f"R {int(d):,}"
    return f"R {d:,.2f}"


def _fmt_pct(value: Any, *, decimals: int = 2) -> str:
    if value is None:
        return ""
    d = Decimal(str(value)) * Decimal("100")
    return f"{d:.{decimals}f}%"


def _fmt_long_date(d: Any) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    if not isinstance(d, date):
        return str(d)
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    return f"{d.day} {months[d.month - 1]} {d.year}"


def _maybe_decode(value: Any) -> Any:
    """Defensive: asyncpg's jsonb codec doesn't reliably decode table-sourced
    columns in 0.31. Same pattern as routers/audit._row_to_entry and
    routers/imports._decode_jsonb."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _build_context(
    snapshot: dict[str, Any],
    branding: Branding,
    *,
    generated_at_iso: str,
) -> dict[str, Any]:
    """Pure assembly. snapshot is a dict-like row from get_with_property."""
    inputs = _maybe_decode(snapshot["inputs_json"]) or {}
    result = _maybe_decode(snapshot["result_json"]) or {}

    if snapshot["source"] == "excel_import" and snapshot.get("source_file"):
        source_label = f"Excel import — {snapshot['source_file']}"
    elif snapshot["source"] == "manual":
        source_label = "Manual entry"
    else:
        source_label = str(snapshot["source"])

    tenants_resolved = []
    for t in result.get("tenants_resolved", []):
        tenants_resolved.append({
            "description": t.get("description", ""),
            "rentable_area_m2": t.get("rentable_area_m2", ""),
            "effective_rent_per_m2_pm": _fmt_money(t.get("effective_rent_per_m2_pm")),
            "monthly_rent": _fmt_money(t.get("monthly_rent")),
            "escalation_cycles_applied": t.get("escalation_cycles_applied", 0),
        })

    parking = []
    for p in inputs.get("parking", []):
        bays = int(p.get("bays", 0))
        rate = Decimal(str(p.get("rate_per_bay_pm", 0)))
        parking.append({
            "bay_type": p.get("bay_type", "other"),
            "bays": bays,
            "rate_per_bay_pm": _fmt_money(rate),
            "monthly_rent": _fmt_money(rate * bays),
        })

    return {
        "branding": {
            "firm_name": branding.firm_name,
            "firm_logo_path": branding.firm_logo_path,
            "firm_address_lines": list(branding.firm_address_lines),
            "firm_contact_lines": list(branding.firm_contact_lines),
        },
        "entity": {"name": snapshot["entity_name"]},
        "property": {
            "name": snapshot["property_name"],
            "address": snapshot["property_address"],
        },
        "snapshot": {
            "id": str(snapshot["id"]),
            "valuation_date": _fmt_long_date(snapshot["valuation_date"]),
            "created_by": (
                snapshot.get("created_by_email")
                or str(snapshot.get("created_by", ""))
            ),
            "engine_version": snapshot["engine_version"],
            "source": source_label,
            "generated_at": generated_at_iso,
            "market_value_formatted": _fmt_money(snapshot["market_value"]),
        },
        "tenants_resolved": tenants_resolved,
        "parking": parking,
        "totals": {
            "gross_monthly_income": _fmt_money(result.get("gross_monthly_income")),
            "gross_annual_income": _fmt_money(result.get("gross_annual_income")),
            "annual_operating_expenses": _fmt_money(
                result.get("annual_operating_expenses")
            ),
            "opex_per_m2_pm": _fmt_money(result.get("opex_per_m2_pm")),
            "opex_pct_of_gai": _fmt_pct(result.get("opex_pct_of_gai")),
            "vacancy_allowance_amount": _fmt_money(
                result.get("vacancy_allowance_amount")
            ),
            "vacancy_pct": _fmt_pct(inputs.get("vacancy_allowance_pct")),
            "annual_net_income": _fmt_money(result.get("annual_net_income")),
            "cap_rate_pct": _fmt_pct(inputs.get("cap_rate")),
            "capitalised_value": _fmt_money(result.get("capitalised_value")),
            "market_value": _fmt_money(result.get("market_value")),
        },
        "warnings": [
            {
                "code": w.get("code", ""),
                "message": w.get("message", ""),
                "field_path": w.get("field_path"),
            }
            for w in result.get("warnings", [])
        ],
    }


def render_snapshot_pdf(
    snapshot: dict[str, Any],
    branding: Branding,
) -> bytes:
    """WeasyPrint render. CPU-bound; route handler wraps with run_in_threadpool."""
    # Local import — keeps module importable in unit tests where the
    # native libs (Pango/Cairo/HarfBuzz) may be missing on Windows hosts.
    from weasyprint import HTML  # type: ignore[import-untyped]
    ctx = _build_context(
        snapshot, branding,
        generated_at_iso=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    template = _jenv.get_template("pdf_template.html")
    html_str = template.render(**ctx)
    return bytes(HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf())
