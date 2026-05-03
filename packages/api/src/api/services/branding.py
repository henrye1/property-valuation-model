"""Loads firm branding from settings into a single immutable dict for
the PDF template. Loaded once at app startup; never re-read per request."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Branding:
    firm_name: str
    firm_logo_path: str | None
    firm_address_lines: list[str]
    firm_contact_lines: list[str]


def _split_pipes(value: str) -> list[str]:
    return [p.strip() for p in value.split("|") if p.strip()]


def load(settings: Any) -> Branding:
    """Build Branding from a Settings instance.

    `settings` is duck-typed (typed as Any) to mirror services/storage.py's
    build_client pattern and avoid circular imports with config.py.

    If BRANDING_FIRM_LOGO_PATH points at a missing file, firm_logo_path is
    set to None — the template renders firm name larger instead.
    """
    raw_path = str(settings.BRANDING_FIRM_LOGO_PATH)
    logo: str | None = raw_path
    if not Path(raw_path).is_file():
        logo = None
    return Branding(
        firm_name=str(settings.BRANDING_FIRM_NAME),
        firm_logo_path=logo,
        firm_address_lines=_split_pipes(str(settings.BRANDING_FIRM_ADDRESS_LINES)),
        firm_contact_lines=_split_pipes(str(settings.BRANDING_FIRM_CONTACT_LINES)),
    )
