"""Command-line interface for Claim Ledger validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .validator import validate_ledger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kcv-validate",
        description="Run deterministic checks against a KCV Claim Ledger.",
    )
    parser.add_argument("ledger", type=Path, help="Path to a ledger JSON file")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}")
        return 2

    if not isinstance(payload, dict):
        if args.as_json:
            print(json.dumps({"ok": False, "error": "Ledger root must be an object."}))
        else:
            print("ERROR: Ledger root must be an object.")
        return 2

    result = validate_ledger(payload)
    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    elif result.ok:
        print("PASS: no deterministic findings")
    else:
        for finding in result.findings:
            location = f" [{finding.claim_id}]" if finding.claim_id else ""
            print(f"{finding.severity} {finding.rule_id}{location}: {finding.message}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

