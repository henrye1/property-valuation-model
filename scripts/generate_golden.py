"""Walk every sample workbook in ``1. VALUATION EXAMPLES/`` and emit golden
inputs+expected JSON pairs into ``packages/valuation_engine/tests/golden/``.

Usage:
    python scripts/generate_golden.py            # generate
    python scripts/generate_golden.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from valuation_engine import calculate
from valuation_engine.excel.parse import (
    RECOMPUTE_TOLERANCE_PCT,
    compute_diff_pct,
    parse_workbook,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = REPO_ROOT / "1. VALUATION EXAMPLES"
GOLDEN = REPO_ROOT / "packages/valuation_engine/tests/golden"
INPUTS_DIR = GOLDEN / "inputs"
EXPECTED_DIR = GOLDEN / "expected"
SKIPPED_LOG = GOLDEN / "skipped.json"


def _slug(path: Path) -> str:
    return path.stem.replace(" ", "_").replace("/", "_")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped: list[dict] = []

    for src in sorted(SAMPLES.iterdir()):
        if src.suffix.lower() != ".xlsx":
            skipped.append(
                {"file": src.name, "reason": "non-xlsx (e.g. .xls); not supported in v1"}
            )
            continue
        try:
            parsed = parse_workbook(src)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            skipped.append({"file": src.name, "reason": f"parser raised: {exc}"})
            continue

        if parsed.inputs is None:
            skipped.append(
                {
                    "file": src.name,
                    "reason": "missing required sections",
                    "errors": [e.model_dump() for e in parsed.parse_errors],
                }
            )
            continue

        result = calculate(parsed.inputs)

        if parsed.sheet_market_value is not None:
            diff = compute_diff_pct(parsed.sheet_market_value, result.market_value)
            if diff is not None and diff > RECOMPUTE_TOLERANCE_PCT:
                skipped.append(
                    {
                        "file": src.name,
                        "reason": "recompute_mismatch beyond tolerance",
                        "sheet_value": str(parsed.sheet_market_value),
                        "recomputed": str(result.market_value),
                        "diff_pct": str(diff),
                    }
                )
                continue

        slug = _slug(src)
        if not args.dry_run:
            (INPUTS_DIR / f"{slug}.json").write_text(
                parsed.inputs.model_dump_json(indent=2)
            )
            (EXPECTED_DIR / f"{slug}.json").write_text(
                result.model_dump_json(indent=2)
            )
        written += 1

    if not args.dry_run:
        SKIPPED_LOG.write_text(json.dumps(skipped, indent=2))
    else:
        # In dry-run, dump the skip list to stdout so reviewers can categorise.
        print(json.dumps(skipped, indent=2))

    print(f"Generated {written} golden pairs; skipped {len(skipped)}.")
    print(f"Skipped log: {SKIPPED_LOG}")
    return 0 if written > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
