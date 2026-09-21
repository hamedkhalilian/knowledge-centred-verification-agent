"""Contract-month expansion, and its reduction to sufficient statistics.

Two steps, and the second is what makes a pure-Python fit viable on a real
book.

**Expansion.** Each contract contributes one row per month from eligibility
until it exits or the observation window closes. A contract still running at
the cut simply stops contributing rows: it is neither counted as a non-event
nor dropped. That is the entire censoring treatment.

**Aggregation.** Once every covariate is binned, contract-months that land in
the same cell are exchangeable, so the likelihood depends on the panel only
through the exposure count and the event counts per cell. A book of 865,000
contracts over 120 months is 100 million rows and a few thousand cells, and
the grouped likelihood is exact — not an approximation of the row-level one.

Maturity is treated as censoring rather than as an event. A contract that
reaches the end of its schedule did not choose anything; the option simply
expired unexercised. Counting it as an exit would put a deterministic event
into a behavioural hazard.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from termination.model import (
    MATURITY,
    MODELLED_CAUSES,
    Contract,
    TermCurve,
)

#: Incentive bin edges in basis points. Dense through the money, where the
#: exercise curve turns, and coarse in the tails, where exposure is thin.
DEFAULT_INCENTIVE_EDGES_BP: tuple[float, ...] = (
    -200.0, -150.0, -100.0, -75.0, -50.0, -25.0,
    0.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0,
)

#: Season bin edges in months since eligibility.
DEFAULT_SEASON_EDGES: tuple[int, ...] = (6, 12, 24, 36, 60)


def bucket(value: float, edges: Sequence[float]) -> int:
    """Index of the half-open bin ``[edges[i-1], edges[i])`` holding ``value``.

    Returns ``0`` below the first edge and ``len(edges)`` at or above the last,
    so the tails are always representable and nothing is silently discarded.
    """
    low, high = 0, len(edges)
    while low < high:
        mid = (low + high) // 2
        if value < edges[mid]:
            high = mid
        else:
            low = mid + 1
    return low


def bucket_label(index: int, edges: Sequence[float], unit: str = "bp") -> str:
    if index == 0:
        return f"< {edges[0]:g}{unit}"
    if index >= len(edges):
        return f">= {edges[-1]:g}{unit}"
    return f"[{edges[index - 1]:g}, {edges[index]:g}){unit}"


@dataclass(frozen=True)
class CellKey:
    """The binned coordinates of a set of exchangeable contract-months."""

    incentive_bin: int
    season_bin: int
    strata: tuple[tuple[str, str], ...] = ()


@dataclass
class Cell:
    """Exposure and event counts for one cell.

    ``exposure`` counts contract-months at risk. ``events`` counts exits by
    cause. Everything the grouped likelihood needs is here.
    """

    key: CellKey
    exposure: int = 0
    events: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    #: Exposure-weighted mean incentive, kept so a fitted curve can be plotted
    #: against the value the cell actually carries rather than its bin centre.
    incentive_sum: float = 0.0
    burnout_sum: float = 0.0

    @property
    def mean_incentive_bp(self) -> float:
        return self.incentive_sum / self.exposure if self.exposure else 0.0

    @property
    def mean_burnout(self) -> float:
        return self.burnout_sum / self.exposure if self.exposure else 0.0

    def event_count(self, cause: str) -> int:
        return self.events.get(cause, 0)

    @property
    def total_events(self) -> int:
        return sum(self.events.values())


@dataclass
class Panel:
    """An aggregated contract-month panel."""

    cells: dict[CellKey, Cell] = field(default_factory=dict)
    incentive_edges: tuple[float, ...] = DEFAULT_INCENTIVE_EDGES_BP
    season_edges: tuple[int, ...] = DEFAULT_SEASON_EDGES
    contracts_expanded: int = 0
    contracts_never_eligible: int = 0

    @property
    def exposure(self) -> int:
        return sum(cell.exposure for cell in self.cells.values())

    def events(self, cause: str) -> int:
        return sum(cell.event_count(cause) for cause in (cause,) for cell in self.cells.values())

    def event_totals(self) -> dict[str, int]:
        totals: dict[str, int] = defaultdict(int)
        for cell in self.cells.values():
            for cause, count in cell.events.items():
                totals[cause] += count
        return dict(totals)

    def ordered_cells(self) -> list[Cell]:
        return [
            self.cells[key]
            for key in sorted(
                self.cells,
                key=lambda k: (k.incentive_bin, k.season_bin, k.strata),
            )
        ]


def build_panel(
    contracts: Iterable[Contract],
    curve: TermCurve,
    *,
    incentive_edges: Sequence[float] = DEFAULT_INCENTIVE_EDGES_BP,
    season_edges: Sequence[int] = DEFAULT_SEASON_EDGES,
    strata_keys: Sequence[str] = (),
    min_month: int | None = None,
    max_month: int | None = None,
    month_predicate: Callable[[Contract, int], bool] | None = None,
) -> Panel:
    """Expand contracts to contract-months and aggregate into cells.

    ``strata_keys`` names covariates read from ``Contract.covariates``. They
    must already be categorical: aggregation is exact only when every
    covariate in the model is binned, and a continuous one silently smuggled
    in here would make the grouped likelihood an approximation instead.

    ``min_month`` and ``max_month`` restrict the calendar window. They exist
    for out-of-time validation: fit on one window, score on the next. Note
    that windowing is *not* the same as censoring the contracts — a contract
    that exits after ``max_month`` correctly contributes exposure and no
    event to the earlier window, which is what right censoring means.

    ``month_predicate`` selects individual contract-months. It exists so that
    a random split can be built the same way a temporal one is, which is what
    makes the two comparable on the same book.
    """
    panel = Panel(
        incentive_edges=tuple(incentive_edges),
        season_edges=tuple(season_edges),
    )

    for contract in contracts:
        start = max(contract.eligible_from, contract.origination_month)
        end = contract.observed_until()
        if min_month is not None:
            start = max(start, min_month)
        if max_month is not None:
            end = min(end, max_month)
        if end < start:
            # Censored or exited before the right ever arose. It carries no
            # information about exercise, so it contributes no exposure —
            # but it is counted, because a book that is mostly ineligible is
            # a fact about the fit, not a detail to discover later.
            panel.contracts_never_eligible += 1
            continue

        panel.contracts_expanded += 1
        burnout = 0.0

        for month in range(start, end + 1):
            remaining = contract.remaining_months(month)
            if remaining <= 0:
                break
            if month_predicate is not None and not month_predicate(contract, month):
                # Burnout still accrues: the month happened, it is merely not
                # in this sample. Skipping the accrual would make the two
                # halves of a split disagree about the same contract's past.
                incentive = (
                    contract.coupon - curve.refi_rate(month, remaining)
                ) * 10_000.0
                burnout += max(incentive, 0.0) / 10_000.0
                continue
            incentive_bp = (
                contract.coupon - curve.refi_rate(month, remaining)
            ) * 10_000.0

            key = CellKey(
                incentive_bin=bucket(incentive_bp, incentive_edges),
                season_bin=bucket(month - contract.eligible_from, season_edges),
                strata=tuple(
                    (name, contract.covariates.get(name, ""))
                    for name in strata_keys
                ),
            )
            cell = panel.cells.get(key)
            if cell is None:
                cell = Cell(key=key)
                panel.cells[key] = cell

            cell.exposure += 1
            cell.incentive_sum += incentive_bp
            cell.burnout_sum += burnout

            is_exit_month = (
                contract.exit_month is not None and month == contract.exit_month
            )
            if is_exit_month and contract.exit_cause in MODELLED_CAUSES:
                cell.events[contract.exit_cause] += 1
            # MATURITY falls through deliberately: exposure counted, no event.

            # Burnout accrues only while the right exists and is declined.
            burnout += max(incentive_bp, 0.0) / 10_000.0

    return panel


__all__ = [
    "Cell",
    "CellKey",
    "Panel",
    "build_panel",
    "bucket",
    "bucket_label",
    "DEFAULT_INCENTIVE_EDGES_BP",
    "DEFAULT_SEASON_EDGES",
    "MATURITY",
]
