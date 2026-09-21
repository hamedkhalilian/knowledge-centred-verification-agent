"""Out-of-time validation, and a demonstration of why it is the only kind.

Efron runs the same algorithm on the same data twice, changing only how the
split is made: random gives 2% test error, splitting by enrolment order gives
24%. The model had learned the period, not the mechanism.

A loan book makes that failure worse, not better. Every contract alive in a
given month sees the *same* refinancing rate, so a random split puts the same
rate month on both sides of the partition for thousands of contracts at once.
The test set is then not independent of the training set in any sense that
matters, and the score it returns is an estimate of nothing.

So this module does not merely provide a temporal split. It runs both splits
on the same book and reports them side by side, because the gap between them
is a measurement of how much of the fit is regime and how much is behaviour.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from termination.model import S489, Contract, TermCurve
from termination.panel import Panel, build_panel, bucket_label


def _stable_fraction(contract_id: str, month: int) -> float:
    """A deterministic pseudo-random number in [0, 1) for a contract-month."""
    digest = hashlib.blake2b(
        f"{contract_id}:{month}".encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


@dataclass
class BinCalibration:
    label: str
    exposure: int
    observed: int
    predicted: float
    #: Contract-months the training sample had in this bin. Reported because
    #: a prediction resting on a few hundred months applied to tens of
    #: thousands is an extrapolation, and the ratio alone does not show it.
    train_exposure: int = 0

    @property
    def ratio(self) -> float:
        return self.observed / self.predicted if self.predicted > 0 else float("nan")

    @property
    def leverage(self) -> float:
        """Test exposure per unit of training exposure in the same bin."""
        return self.exposure / self.train_exposure if self.train_exposure else float("inf")

    @property
    def unseen(self) -> bool:
        return self.train_exposure == 0


@dataclass
class Calibration:
    """How well hazards fitted on one sample predict counts in another."""

    kind: str
    bins: list[BinCalibration]
    observed: int
    predicted: float

    @property
    def ratio(self) -> float:
        return self.observed / self.predicted if self.predicted > 0 else float("nan")

    @property
    def unseen_exposure(self) -> int:
        """Test contract-months in bins the training sample never populated.

        The headline extrapolation number. No hazard was estimated there, so
        the predicted count is zero by construction and the observed events
        are pure surprise.
        """
        return sum(b.exposure for b in self.bins if b.unseen)

    @property
    def unseen_events(self) -> int:
        return sum(b.observed for b in self.bins if b.unseen)

    @property
    def absolute_error(self) -> float:
        """Mean absolute deviation of the per-bin ratio from one.

        Weighted by predicted events, so a thin bin cannot dominate. This is
        the number to compare across split kinds.
        """
        total = sum(b.predicted for b in self.bins if b.predicted > 0)
        if total <= 0:
            return float("nan")
        return sum(
            b.predicted * abs(b.ratio - 1.0)
            for b in self.bins
            if b.predicted > 0
        ) / total

    def render(self) -> str:
        rows = [
            f"{self.kind} split — predicted {self.predicted:,.1f}, "
            f"observed {self.observed:,}, ratio {self.ratio:.3f}, "
            f"weighted |error| {self.absolute_error:.3f}",
            f"{'incentive':>18} {'train exp':>10} {'test exp':>10} {'obs':>6} "
            f"{'pred':>9} {'ratio':>7}  note",
        ]
        for b in self.bins:
            if b.exposure == 0:
                continue
            if b.unseen:
                note = "UNSEEN in training"
            elif b.leverage > 10:
                note = f"extrapolating {b.leverage:.0f}x"
            else:
                note = ""
            ratio = "     —" if b.predicted <= 0 else f"{b.ratio:>7.3f}"
            rows.append(
                f"{b.label:>18} {b.train_exposure:>10,} {b.exposure:>10,} "
                f"{b.observed:>6,} {b.predicted:>9.1f} {ratio}  {note}"
            )
        if self.unseen_exposure:
            rows.append("")
            rows.append(
                f"{self.unseen_exposure:,} test contract-months and "
                f"{self.unseen_events:,} events fall in bins the training "
                "sample never populated. No hazard was estimated there."
            )
        return "\n".join(rows)


def _hazards_by_bin(panel: Panel, cause: str) -> dict[int, float]:
    exposure: dict[int, int] = {}
    events: dict[int, int] = {}
    for cell in panel.cells.values():
        index = cell.key.incentive_bin
        exposure[index] = exposure.get(index, 0) + cell.exposure
        events[index] = events.get(index, 0) + cell.event_count(cause)
    return {
        index: events[index] / exposure[index]
        for index in exposure
        if exposure[index] > 0
    }


def calibrate(
    train: Panel, test: Panel, *, kind: str, cause: str = S489
) -> Calibration:
    """Apply the training hazards to the test exposure and compare counts.

    A test bin the training sample never populated is reported with a
    predicted count of zero rather than an imputed one. Extrapolating into an
    incentive range the fit never saw is the specific failure this whole
    module exists to expose.
    """
    hazards = _hazards_by_bin(train, cause)
    train_exposure: dict[int, int] = {}
    for cell in train.cells.values():
        index = cell.key.incentive_bin
        train_exposure[index] = train_exposure.get(index, 0) + cell.exposure
    exposure: dict[int, int] = {}
    observed: dict[int, int] = {}
    for cell in test.cells.values():
        index = cell.key.incentive_bin
        exposure[index] = exposure.get(index, 0) + cell.exposure
        observed[index] = observed.get(index, 0) + cell.event_count(cause)

    bins = [
        BinCalibration(
            label=bucket_label(index, test.incentive_edges),
            exposure=exposure[index],
            observed=observed[index],
            predicted=hazards.get(index, 0.0) * exposure[index],
            train_exposure=train_exposure.get(index, 0),
        )
        for index in sorted(exposure)
    ]
    return Calibration(
        kind=kind,
        bins=bins,
        observed=sum(observed.values()),
        predicted=sum(b.predicted for b in bins),
    )


def temporal_calibration(
    contracts: list[Contract],
    curve: TermCurve,
    split_month: int,
    *,
    cause: str = S489,
    **panel_kwargs,
) -> Calibration:
    """Fit on everything up to ``split_month``, score on everything after."""
    train = build_panel(contracts, curve, max_month=split_month, **panel_kwargs)
    test = build_panel(contracts, curve, min_month=split_month + 1, **panel_kwargs)
    return calibrate(train, test, kind="temporal", cause=cause)


def random_calibration(
    contracts: list[Contract],
    curve: TermCurve,
    *,
    train_share: float = 0.5,
    cause: str = S489,
    **panel_kwargs,
) -> Calibration:
    """The split that flatters. Provided so the flattery can be measured."""
    train = build_panel(
        contracts,
        curve,
        month_predicate=lambda c, m: _stable_fraction(c.contract_id, m) < train_share,
        **panel_kwargs,
    )
    test = build_panel(
        contracts,
        curve,
        month_predicate=lambda c, m: _stable_fraction(c.contract_id, m) >= train_share,
        **panel_kwargs,
    )
    return calibrate(train, test, kind="random", cause=cause)


__all__ = [
    "BinCalibration",
    "Calibration",
    "calibrate",
    "temporal_calibration",
    "random_calibration",
]
