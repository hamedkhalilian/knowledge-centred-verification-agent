"""Command-line interface for the §489 termination model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from termination.curve import empirical_exercise_curve
from termination.load import read_contracts, read_rates, write_contracts
from termination.model import MODELLED_CAUSES, S489
from termination.panel import build_panel
from termination.synth import generate
from termination.validation import random_calibration, temporal_calibration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termination",
        description="Measure the §489 exercise curve from a loan book.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("curve", "Empirical exercise curve by refinancing incentive"),
        ("validate", "Compare a random split against a temporal one"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--contracts", type=Path, help="contracts CSV")
        p.add_argument("--rates", type=Path, help="rates CSV")
        p.add_argument(
            "--slope",
            type=float,
            default=0.0,
            help="term premium per year of remaining maturity, as a decimal",
        )
        p.add_argument(
            "--synthetic",
            type=int,
            metavar="N",
            help="use N synthetic contracts instead of CSV input",
        )
        p.add_argument("--seed", type=int, default=20260921)
        p.add_argument("--cause", default=S489, choices=sorted(MODELLED_CAUSES))
        if name == "validate":
            p.add_argument(
                "--split-month",
                type=int,
                required=True,
                help="last calendar month of the training window",
            )

    emit = sub.add_parser("synth", help="Write a synthetic book to CSV")
    emit.add_argument("--out", type=Path, required=True)
    emit.add_argument("--contracts-count", type=int, default=4000)
    emit.add_argument("--seed", type=int, default=20260921)

    return parser


def _load(args) -> tuple[list, object]:
    if args.synthetic:
        contracts, curve, _ = generate(n_contracts=args.synthetic, seed=args.seed)
        return contracts, curve
    if not args.contracts or not args.rates:
        raise SystemExit(
            "provide --contracts and --rates, or --synthetic N for a dry run"
        )
    return read_contracts(args.contracts), read_rates(args.rates, slope=args.slope)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "synth":
        contracts, _, _ = generate(
            n_contracts=args.contracts_count, seed=args.seed
        )
        write_contracts(contracts, args.out)
        print(f"wrote {len(contracts):,} contracts to {args.out}")
        return 0

    try:
        contracts, curve = _load(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.command == "curve":
        panel = build_panel(contracts, curve)
        exercise = empirical_exercise_curve(panel, cause=args.cause)
        if args.as_json:
            print(json.dumps(
                {
                    "cause": exercise.cause,
                    "exposure": exercise.total_exposure,
                    "events": exercise.total_events,
                    "event_totals": panel.event_totals(),
                    "contracts_never_eligible": panel.contracts_never_eligible,
                    "points": [
                        {
                            "label": p.label,
                            "mean_incentive_bp": round(p.mean_incentive_bp, 2),
                            "exposure": p.exposure,
                            "events": p.events,
                            "monthly_hazard": p.hazard,
                            "annual_hazard": p.annual_hazard,
                            "annual_ci": p.annual_interval,
                        }
                        for p in exercise.points
                    ],
                    "monotonicity_violations": exercise.monotonicity_violations(),
                },
                indent=2,
            ))
        else:
            totals = panel.event_totals()
            print(exercise.render())
            print()
            print(f"all exits: {totals}")
            if panel.contracts_never_eligible:
                print(
                    f"{panel.contracts_never_eligible:,} contracts never reached "
                    "eligibility and contribute no exposure"
                )
        return 0

    if args.command == "validate":
        temporal = temporal_calibration(
            contracts, curve, args.split_month, cause=args.cause
        )
        chance = random_calibration(contracts, curve, cause=args.cause)
        if args.as_json:
            print(json.dumps(
                {
                    kind.kind: {
                        "observed": kind.observed,
                        "predicted": kind.predicted,
                        "ratio": kind.ratio,
                        "weighted_abs_error": kind.absolute_error,
                    }
                    for kind in (chance, temporal)
                },
                indent=2,
            ))
        else:
            print(chance.render())
            print()
            print(temporal.render())
            print()
            gap = temporal.absolute_error - chance.absolute_error
            print(
                f"temporal error exceeds random by {gap:+.3f}. The random split "
                "shares rate months between train and test, so the gap is a "
                "lower bound on how much of the fit is regime rather than "
                "behaviour."
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
