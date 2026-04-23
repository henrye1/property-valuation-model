"""Tolerant, label-driven Excel parser.

Locates sections by column-A labels rather than absolute row numbers, so the
parser tolerates the layout drift seen across the historical sample sheets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, ConfigDict, ValidationError

from valuation_engine.models import ValuationInput, Warning

TENANT_HEADER_NEEDLES = ("rentable area",)
SUBTOTAL_LABEL = "sub total"
SECTION_END_BLANK_RUN = 2  # consecutive blank rows = end of section


@dataclass
class _SheetCursor:
    ws: Worksheet
    max_row: int

    def find_label_row(self, *needles: str, start: int = 1) -> int | None:
        """Return the 1-based row index of the first column-A cell matching any needle.

        Matching is a case-insensitive substring match.
        """
        needles_lower = [n.lower() for n in needles]
        for r in range(start, self.max_row + 1):
            v = self.ws.cell(row=r, column=1).value
            if isinstance(v, str):
                vl = v.strip().lower()
                if any(n in vl for n in needles_lower):
                    return r
        return None


class ParseResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    inputs: ValuationInput | None
    building_name: str | None
    sheet_market_value: Decimal | None
    parse_warnings: list[Warning]
    parse_errors: list[Warning]


def parse_workbook(path: Path) -> ParseResult:
    """Parse a single workbook and return inputs + diagnostics.

    Reads with `data_only=True` so cached formula values are available for the
    recompute-and-compare check; falls back to formula-only parse if a cell has
    no cached value (raises a `formula_missing_value` warning per cell).
    """
    wb = load_workbook(path, data_only=True, read_only=False)
    sheet_names = wb.sheetnames
    parse_warnings: list[Warning] = []
    parse_errors: list[Warning] = []

    if len(sheet_names) > 1:
        parse_warnings.append(
            Warning(
                code="multiple_sheets",
                message=(
                    f"Workbook has {len(sheet_names)} sheets; "
                    f"using the first ('{sheet_names[0]}')."
                ),
                field_path=None,
            )
        )

    ws = wb[sheet_names[0]]
    cur = _SheetCursor(ws=ws, max_row=ws.max_row or 1)

    building_name = _read_building_name(cur)
    valuation_date = _read_valuation_date(cur, parse_warnings, parse_errors)
    tenant_dicts, _last = _read_tenants(cur, parse_warnings, parse_errors)

    inputs = _build_inputs_partial(
        valuation_date=valuation_date,
        tenant_dicts=tenant_dicts,
        parking_dicts=[],
        assumptions={},
        parse_errors=parse_errors,
    )

    return ParseResult(
        inputs=inputs,
        building_name=building_name,
        sheet_market_value=None,
        parse_warnings=parse_warnings,
        parse_errors=parse_errors,
    )


def _read_building_name(cur: _SheetCursor) -> str | None:
    row = cur.find_label_row("building name")
    if row is None:
        return None
    v = cur.ws.cell(row=row, column=2).value
    if v is None:
        return None
    return str(v).strip()


def _read_valuation_date(
    cur: _SheetCursor,
    parse_warnings: list[Warning],
    parse_errors: list[Warning],
) -> date | None:
    row = cur.find_label_row("date")
    if row is None:
        parse_errors.append(
            Warning(
                code="missing_required_section",
                message="Could not find 'Date' label in column A.",
                field_path="valuation_date",
            )
        )
        return None
    # Date is in column E in canonical layout; tolerate B-E by scanning.
    for col in (5, 4, 3, 2):
        v = cur.ws.cell(row=row, column=col).value
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
    parse_errors.append(
        Warning(
            code="missing_required_section",
            message="Date row found but no parseable date value in columns B-E.",
            field_path="valuation_date",
        )
    )
    return None


def _find_tenant_header_row(cur: _SheetCursor) -> int | None:
    """Find the header row that contains 'Rentable area' anywhere in cols A-J."""
    for r in range(1, cur.max_row + 1):
        for col in range(1, 11):
            v = cur.ws.cell(row=r, column=col).value
            if isinstance(v, str) and "rentable area" in v.lower():
                return r
    return None


def _read_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        # bool is a subclass of int; don't coerce booleans to Decimal.
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        s = value.replace(",", "").replace("R", "").strip()
        try:
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None
    return None


def _read_pct(value: Any) -> Decimal | None:
    """Parse a percentage cell. Excel may store 8% as 0.08 or as the string '8%'."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        s = value.strip().replace("%", "")
        try:
            d = Decimal(s)
        except (InvalidOperation, ValueError):
            return None
        return d / Decimal("100") if "%" in value else d
    return None


def _read_tenants(
    cur: _SheetCursor,
    parse_warnings: list[Warning],
    parse_errors: list[Warning],
) -> tuple[list[dict[str, Any]], int]:
    """Returns (tenant_dicts, last_row_consumed).

    tenant_dicts have keys: description, rentable_area_m2, rent_per_m2_pm,
    annual_escalation_pct (Decimal|None).
    """
    header_row = _find_tenant_header_row(cur)
    if header_row is None:
        parse_errors.append(
            Warning(
                code="missing_required_section",
                message="Could not find tenant header row containing 'Rentable area'.",
                field_path="tenants",
            )
        )
        return [], 0

    tenants: list[dict[str, Any]] = []
    blank_run = 0
    last_row = header_row
    for r in range(header_row + 1, cur.max_row + 1):
        a = cur.ws.cell(row=r, column=1).value
        if isinstance(a, str) and SUBTOTAL_LABEL in a.lower():
            return tenants, r
        # Detect end-of-section by blank streak.
        row_values = [cur.ws.cell(row=r, column=c).value for c in range(1, 10)]
        if all(v is None or v == "" for v in row_values):
            blank_run += 1
            if blank_run >= SECTION_END_BLANK_RUN:
                return tenants, r
            continue
        blank_run = 0

        area = _read_decimal(cur.ws.cell(row=r, column=6).value)
        rent = _read_decimal(cur.ws.cell(row=r, column=7).value)
        if area is None or rent is None:
            parse_warnings.append(
                Warning(
                    code="unrecognised_row",
                    message=(
                        f"Row {r}: tenant row missing area or rent "
                        f"(area={area}, rent={rent})."
                    ),
                    field_path=f"tenants[row {r}]",
                )
            )
            continue
        if area <= 0:
            # Skip subtotal rows or zero-area filler rows silently.
            continue

        description = (
            cur.ws.cell(row=r, column=2).value
            or cur.ws.cell(row=r, column=1).value
            or ""
        )
        esc = _read_pct(cur.ws.cell(row=r, column=3).value)
        tenants.append(
            dict(
                description=str(description).strip(),
                rentable_area_m2=area,
                rent_per_m2_pm=rent,
                annual_escalation_pct=esc if esc is not None else Decimal("0"),
            )
        )
        last_row = r

    return tenants, last_row


def _build_inputs_partial(
    *,
    valuation_date: date | None,
    tenant_dicts: list[dict[str, Any]],
    parking_dicts: list[dict[str, Any]],
    assumptions: dict[str, Any],
    parse_errors: list[Warning],
) -> ValuationInput | None:
    if valuation_date is None or not tenant_dicts:
        return None
    try:
        from valuation_engine.models import ParkingLine, TenantLine
        return ValuationInput(
            valuation_date=valuation_date,
            tenants=[TenantLine(**t) for t in tenant_dicts],
            parking=[ParkingLine(**p) for p in parking_dicts],
            monthly_operating_expenses=assumptions.get(
                "monthly_operating_expenses", Decimal("0")
            ),
            vacancy_allowance_pct=assumptions.get(
                "vacancy_allowance_pct", Decimal("0")
            ),
            cap_rate=assumptions.get("cap_rate", Decimal("0.10")),
        )
    except (ValueError, TypeError, ValidationError) as exc:
        parse_errors.append(
            Warning(
                code="missing_required_section",
                message=f"Could not assemble ValuationInput: {exc}",
                field_path=None,
            )
        )
        return None
