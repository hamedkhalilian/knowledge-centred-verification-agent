"""Reading a real book from CSV.

Two files, both plain CSV, because the point is that a risk analyst can
inspect and correct the input without a database round trip.

**contracts.csv** — one row per contract:

``contract_id,coupon,balance,term_months,origination_month,eligible_from,
last_observed,exit_month,exit_cause`` plus any number of extra columns, which
become categorical covariates.

Months are integer indices on one shared calendar, not dates. That is
deliberate: the model never needs a real date, and integers remove an entire
class of timezone and day-count mistakes at the boundary.

``exit_month`` and ``exit_cause`` are empty for a contract still running.
An exit whose cause was not recorded must be spelled out rather than left
blank, because an unknown cause is a limitation of the data and silently
treating it as censoring would understate every hazard.

**rates.csv** — ``month,rate`` with ``rate`` a decimal, one row per month.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from termination.model import Contract, PathCurve

RESERVED = {
    "contract_id",
    "coupon",
    "balance",
    "term_months",
    "origination_month",
    "eligible_from",
    "last_observed",
    "exit_month",
    "exit_cause",
}


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


def read_contracts(path: Path | str) -> list[Contract]:
    """Load contracts, failing loudly on the row that is wrong."""
    out: list[Contract] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                cause = (row.get("exit_cause") or "").strip() or None
                out.append(
                    Contract(
                        contract_id=row["contract_id"],
                        coupon=float(row["coupon"]),
                        balance=float(row["balance"]),
                        term_months=int(row["term_months"]),
                        origination_month=int(row["origination_month"]),
                        eligible_from=int(row["eligible_from"]),
                        last_observed=int(row["last_observed"]),
                        exit_month=_optional_int(row.get("exit_month")),
                        exit_cause=cause,
                        covariates={
                            key: value
                            for key, value in row.items()
                            if key not in RESERVED and value not in (None, "")
                        },
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"{path}: line {line_number}: {exc}"
                ) from exc
    return out


def read_rates(path: Path | str, slope: float = 0.0) -> PathCurve:
    """Load a monthly rate path indexed by month.

    Missing months are carried forward from the previous observation, and a
    gap at the start is an error rather than a zero.
    """
    by_month: dict[int, float] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_month[int(row["month"])] = float(row["rate"])
    if not by_month:
        raise ValueError(f"{path}: no rates")
    highest = max(by_month)
    if 0 not in by_month and min(by_month) > 0:
        raise ValueError(
            f"{path}: rates start at month {min(by_month)}; the path must "
            "cover month 0 or be re-indexed"
        )
    path_values: list[float] = []
    last = by_month[min(by_month)]
    for month in range(highest + 1):
        last = by_month.get(month, last)
        path_values.append(last)
    return PathCurve(path=tuple(path_values), slope=slope)


def write_contracts(contracts: list[Contract], path: Path | str) -> None:
    """Round-trip helper, used to emit a synthetic book for inspection."""
    extra = sorted({key for c in contracts for key in c.covariates})
    columns = [
        "contract_id", "coupon", "balance", "term_months",
        "origination_month", "eligible_from", "last_observed",
        "exit_month", "exit_cause", *extra,
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for c in contracts:
            row = {
                "contract_id": c.contract_id,
                "coupon": c.coupon,
                "balance": c.balance,
                "term_months": c.term_months,
                "origination_month": c.origination_month,
                "eligible_from": c.eligible_from,
                "last_observed": c.last_observed,
                "exit_month": "" if c.exit_month is None else c.exit_month,
                "exit_cause": c.exit_cause or "",
            }
            row.update({key: c.covariates.get(key, "") for key in extra})
            writer.writerow(row)


__all__ = ["read_contracts", "read_rates", "write_contracts"]
