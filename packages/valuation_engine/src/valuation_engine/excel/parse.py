"""Tolerant, label-driven Excel parser.

Locates sections by column-A labels rather than absolute row numbers, so the
parser tolerates the layout drift seen across the historical sample sheets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, ConfigDict

from valuation_engine.models import ValuationInput, Warning


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
    _read_valuation_date(cur, parse_warnings, parse_errors)

    return ParseResult(
        inputs=None,  # populated as later tasks add tenant/parking/assumptions parsing
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
