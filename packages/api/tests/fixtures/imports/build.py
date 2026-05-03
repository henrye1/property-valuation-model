"""Build the synthetic Excel fixtures used by the imports integration tests.

Run manually:
    cd packages/api
    env -u VIRTUAL_ENV uv run --no-sync --extra dev python tests/fixtures/imports/build.py

Output: 9 .xlsx files in this directory. Commit them as binaries.
"""
from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from valuation_engine import calculate
from valuation_engine.excel import render_workbook
from valuation_engine.models import ParkingLine, TenantLine, ValuationInput

HERE = Path(__file__).resolve().parent


def _canonical_inputs() -> ValuationInput:
    return ValuationInput(
        valuation_date=date(2026, 3, 15),
        tenants=[
            TenantLine(
                description="Acme Co. (Office)",
                tenant_name="Acme Co.",
                rentable_area_m2=Decimal("250"),
                rent_per_m2_pm=Decimal("180"),
                annual_escalation_pct=Decimal("0.08"),
                next_escalation_date=date(2026, 7, 1),
                lease_period_text="3 yr",
                lease_expiry_date=date(2028, 6, 30),
            ),
        ],
        parking=[
            ParkingLine(
                bay_type="open",
                bays=10,
                rate_per_bay_pm=Decimal("500"),
            )
        ],
        monthly_operating_expenses=Decimal("18000"),
        vacancy_allowance_pct=Decimal("0.05"),
        cap_rate=Decimal("0.10"),
    )


def _render_to(path: Path, *, building_name: str, inputs: ValuationInput) -> None:
    result = calculate(inputs)
    render_workbook(path, building_name=building_name, inputs=inputs, result=result)


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    inputs = _canonical_inputs()

    # 1. canonical.xlsx — happy path, every section present.
    _render_to(HERE / "canonical.xlsx", building_name="55 Empire Road", inputs=inputs)

    # 2. canonical_no_parking.xlsx — parking section absent.
    no_parking = inputs.model_copy(update={"parking": []})
    _render_to(
        HERE / "canonical_no_parking.xlsx",
        building_name="55 Empire Road",
        inputs=no_parking,
    )

    # 3. canonical_multi_sheet.xlsx — second sheet appended after rendering.
    src = HERE / "canonical.xlsx"
    dst = HERE / "canonical_multi_sheet.xlsx"
    shutil.copy(src, dst)
    wb = load_workbook(dst)
    wb.create_sheet("notes")
    wb.save(dst)

    # 4. label_drift_minor.xlsx — one column-A label changed (per Q3-A: → error).
    drift = HERE / "label_drift_minor.xlsx"
    shutil.copy(src, drift)
    wb = load_workbook(drift)
    ws = wb.active
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and "rentable area" in v.lower():
            ws.cell(row=r, column=6, value="Footprint area")  # break the anchor
            break
    wb.save(drift)

    # 5. missing_tenants.xlsx — drop the entire tenant section.
    miss = HERE / "missing_tenants.xlsx"
    shutil.copy(src, miss)
    wb = load_workbook(miss)
    ws = wb.active
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and "rentable area" in v.lower():
            ws.delete_rows(r, amount=1)
            break
    wb.save(miss)

    # 6. recompute_mismatch.xlsx — overwrite the cached market value cell.
    mm = HERE / "recompute_mismatch.xlsx"
    shutil.copy(src, mm)
    wb = load_workbook(mm)
    ws = wb.active
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and "open market assessment" in v.lower():
            ws.cell(row=r, column=9, value=99999999)  # very different
            break
    wb.save(mm)

    # 7. exact_name_match.xlsx — building name matches a seeded property.
    _render_to(
        HERE / "exact_name_match.xlsx",
        building_name="EXACT MATCH PROPERTY",
        inputs=inputs,
    )

    # 8. fuzzy_name_match.xlsx — close but not exact.
    _render_to(
        HERE / "fuzzy_name_match.xlsx",
        building_name="55 Empire Rd",  # Rd vs Road
        inputs=inputs,
    )

    # 9. corrupt.xlsx — not a valid xlsx (just plain text bytes with the
    #    extension). Forces openpyxl into a hard parse failure.
    (HERE / "corrupt.xlsx").write_bytes(b"this is not a real xlsx file")

    print(f"wrote 9 fixtures to {HERE}")


if __name__ == "__main__":
    main()
