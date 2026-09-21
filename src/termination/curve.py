"""The exercise curve, measured before it is modelled.

The headline artefact is a ratio of counts to exposure:

    h(bin) = §489 exits in bin / contract-months at risk in bin

No model, no link function, no assumption about shape. Whatever the
parametric fit later says, it has to agree with this or it is wrong about the
data rather than insightful about it.

Two things are reported alongside every point, because a hazard is a
proportion and proportions from thin cells lie:

* a Wilson score interval, which behaves at the small counts that dominate
  the tails of the incentive range, where the normal interval would put the
  lower bound below zero;
* the exposure itself, so a bin resting on two hundred contract-months is
  visibly not the same evidence as one resting on two million.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from termination.model import S489
from termination.panel import Panel, bucket_label

#: 95% two-sided normal quantile.
Z95 = 1.959963984540054


def wilson_interval(successes: int, trials: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Chosen over the normal interval because monthly hazards are small and
    cell counts in the tails are tiny, exactly where the normal interval
    stops being usable.
    """
    if trials <= 0:
        return (0.0, 0.0)
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denominator
    margin = (
        z / denominator
        * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def annualise(monthly_hazard: float) -> float:
    """Convert a monthly hazard to the implied annual exercise probability."""
    return 1.0 - (1.0 - monthly_hazard) ** 12


@dataclass(frozen=True)
class CurvePoint:
    incentive_bin: int
    label: str
    mean_incentive_bp: float
    exposure: int
    events: int

    @property
    def hazard(self) -> float:
        return self.events / self.exposure if self.exposure else 0.0

    @property
    def annual_hazard(self) -> float:
        return annualise(self.hazard)

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.events, self.exposure)

    @property
    def annual_interval(self) -> tuple[float, float]:
        low, high = self.interval
        return (annualise(low), annualise(high))


@dataclass
class ExerciseCurve:
    """The measured relationship between refinancing incentive and exercise."""

    cause: str
    points: list[CurvePoint]
    total_exposure: int
    total_events: int

    def monotonicity_violations(self) -> list[tuple[str, str]]:
        """Adjacent bins where the hazard falls as the incentive rises.

        The curve is expected to be non-decreasing in the incentive. A
        violation is a signal, not an error: usually a thin cell, sometimes a
        real composition effect worth chasing. Reported, never smoothed away.
        """
        violations: list[tuple[str, str]] = []
        ordered = [p for p in self.points if p.exposure > 0]
        for previous, current in zip(ordered, ordered[1:]):
            if current.hazard < previous.hazard:
                lower, _ = current.interval
                _, upper = previous.interval
                if lower > 0 or upper > 0:
                    violations.append((previous.label, current.label))
        return violations

    def render(self, width: int = 44) -> str:
        """A text plot. The point is to look at the curve, not to admire it."""
        rows = [
            f"exercise curve — cause {self.cause!r}",
            f"exposure {self.total_exposure:,} contract-months, "
            f"{self.total_events:,} events",
            "",
            f"{'incentive':>18}  {'exposure':>11}  {'ev':>5}  "
            f"{'annual':>7}  {'95% CI':>15}",
        ]
        peak = max((p.annual_hazard for p in self.points), default=0.0)
        for point in self.points:
            if point.exposure == 0:
                continue
            low, high = point.annual_interval
            bar_len = int(round(width * point.annual_hazard / peak)) if peak else 0
            rows.append(
                f"{point.label:>18}  {point.exposure:>11,}  {point.events:>5,}  "
                f"{point.annual_hazard:>6.2%}  "
                f"[{low:>5.2%},{high:>6.2%}]  {'#' * bar_len}"
            )
        violations = self.monotonicity_violations()
        if violations:
            rows.append("")
            rows.append("hazard falls as incentive rises between:")
            rows += [f"  {a} -> {b}" for a, b in violations]
        return "\n".join(rows)


def empirical_exercise_curve(panel: Panel, cause: str = S489) -> ExerciseCurve:
    """Collapse the panel onto the incentive axis for one exit cause."""
    exposure: dict[int, int] = {}
    events: dict[int, int] = {}
    incentive_sum: dict[int, float] = {}

    for cell in panel.cells.values():
        index = cell.key.incentive_bin
        exposure[index] = exposure.get(index, 0) + cell.exposure
        events[index] = events.get(index, 0) + cell.event_count(cause)
        incentive_sum[index] = incentive_sum.get(index, 0.0) + cell.incentive_sum

    points = [
        CurvePoint(
            incentive_bin=index,
            label=bucket_label(index, panel.incentive_edges),
            mean_incentive_bp=(
                incentive_sum[index] / exposure[index] if exposure[index] else 0.0
            ),
            exposure=exposure[index],
            events=events[index],
        )
        for index in sorted(exposure)
    ]
    return ExerciseCurve(
        cause=cause,
        points=points,
        total_exposure=sum(exposure.values()),
        total_events=sum(events.values()),
    )


def survival(monthly_hazards: list[float]) -> list[float]:
    """Discrete-time survival, the running product of one minus the hazard."""
    out: list[float] = []
    alive = 1.0
    for hazard in monthly_hazards:
        alive *= max(0.0, 1.0 - hazard)
        out.append(alive)
    return out


__all__ = [
    "CurvePoint",
    "ExerciseCurve",
    "empirical_exercise_curve",
    "survival",
    "wilson_interval",
    "annualise",
    "Z95",
]
