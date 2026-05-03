"""Integration tests for GET /snapshots/{id}/export.pdf.

Marked integration (not pdf) because the headers + 304 behaviour is what we
test here; visual fidelity is the pdf-mark suite (Task 27).

Skipped in environments where WeasyPrint cannot load its native deps
(Pango/Cairo/HarfBuzz). Linux CI installs them via apt (Task 31).
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest


def _weasyprint_unavailable() -> bool:
    """True when WeasyPrint can't render a PDF — typically a missing native
    dependency on Windows hosts without GTK/Pango/Cairo installed.

    Both the import and the actual PDF render are exercised because
    `import weasyprint` succeeds even when libgobject/libpango are missing —
    the failure surfaces only on the first `HTML(...).write_pdf()` call.
    """
    try:
        from weasyprint import HTML
    except Exception:
        return True
    try:
        HTML(string="<p>x</p>").write_pdf()
    except Exception:
        return True
    return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        _weasyprint_unavailable(),
        reason=(
            "WeasyPrint native libs (Pango/Cairo/HarfBuzz) unavailable; "
            "install GTK runtime on Windows or apt-install on Linux. CI runs "
            "these tests once Task 31 lands."
        ),
    ),
]


async def _seed_snapshot(client: Any) -> str:
    # Same shape as the xlsx test — duplicated so this test file is independent.
    ent = await client.post(
        "/entities",
        json={
            "name": "PDF Test Trust",
            "registration_number": None,
            "notes": None,
        },
    )
    eid = ent.json()["id"]
    prop = await client.post(
        "/properties",
        json={
            "entity_id": eid,
            "name": "PDF Test Prop",
            "address": "1 PDF St",
            "property_type": "office",
            "notes": None,
        },
    )
    pid = prop.json()["id"]
    snap = await client.post(
        f"/properties/{pid}/snapshots",
        json={
            "valuation_date": "2026-03-15",
            "tenants": [
                {
                    "description": "T1",
                    "tenant_name": None,
                    "rentable_area_m2": "100",
                    "rent_per_m2_pm": "150",
                    "annual_escalation_pct": "0.08",
                    "next_escalation_date": None,
                    "lease_period_text": None,
                    "lease_expiry_date": None,
                }
            ],
            "parking": [],
            "monthly_operating_expenses": "10000",
            "vacancy_allowance_pct": "0.05",
            "cap_rate": "0.10",
        },
    )
    assert snap.status_code == 201, snap.text
    return str(snap.json()["id"])


async def test_get_pdf_returns_bytes_with_headers(
    viewer_client: Any, valuer_client: Any
) -> None:
    snap_id = await _seed_snapshot(valuer_client)
    resp = await viewer_client.get(f"/snapshots/{snap_id}/export.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers["etag"] == f'"{snap_id}"'
    # Magic bytes — every PDF starts with %PDF.
    assert resp.content[:4] == b"%PDF"


async def test_get_pdf_304_on_matching_etag(
    viewer_client: Any, valuer_client: Any
) -> None:
    snap_id = await _seed_snapshot(valuer_client)
    resp = await viewer_client.get(
        f"/snapshots/{snap_id}/export.pdf",
        headers={"If-None-Match": f'"{snap_id}"'},
    )
    assert resp.status_code == 304


async def test_get_pdf_404_unknown(viewer_client: Any) -> None:
    resp = await viewer_client.get(f"/snapshots/{uuid4()}/export.pdf")
    assert resp.status_code == 404
