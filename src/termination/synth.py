"""A synthetic book with a known exercise curve.

Verification by inversion, the same discipline the migration protocol uses:
generate contracts from a curve that is known exactly, run the estimator, and
check that what comes back is the curve that went in. A pipeline that cannot
recover a truth it was handed has no business being pointed at a real book.

The generated world is deliberately unkind in the ways a real one is:

* three competing exits, only one of which responds to rates, so a pooled
  estimate has something to be attenuated by;
* a rate path that falls and then rises, so the incentive spans both signs
  and the curve is identified on both branches;
* contracts that are censored at the observation cut, disproportionately the
  ones that never exercised.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from termination.model import (
    DEFAULT,
    MATURITY,
    S489,
    SALE,
    Contract,
    PathCurve,
    STATUTORY_LOCKOUT_MONTHS,
)


@dataclass(frozen=True)
class Truth:
    """The exercise curve the generator draws from, in monthly hazards.

    ``h_max / (1 + exp(-steepness * (incentive_bp - centre_bp)))`` for §489,
    plus flat competing hazards. ``burnout`` multiplies the §489 hazard by
    ``exp(-burnout * cumulative_positive_incentive)``.
    """

    h_max: float = 0.030
    steepness: float = 0.030
    centre_bp: float = 0.0
    burnout: float = 0.0
    h_sale: float = 0.0020
    h_default: float = 0.0005

    def s489_hazard(self, incentive_bp: float, burnout_state: float = 0.0) -> float:
        logistic = self.h_max / (
            1.0 + math.exp(-self.steepness * (incentive_bp - self.centre_bp))
        )
        return logistic * math.exp(-self.burnout * burnout_state)


def default_rate_path(months: int) -> tuple[float, ...]:
    """A path that falls from 4% to 2% and climbs back past 5%.

    Both branches matter. A book whose history contains only falling rates
    cannot identify the in-the-money branch of the curve, and no amount of
    in-sample fit will reveal that.
    """
    path = []
    for month in range(months):
        phase = month / max(1, months - 1)
        if phase < 0.5:
            level = 0.04 - 0.04 * phase          # 4% down to 2%
        else:
            level = 0.02 + 0.06 * (phase - 0.5)  # 2% up to 5%
        path.append(level)
    return tuple(path)


def generate(
    n_contracts: int = 4000,
    *,
    seed: int = 20260921,
    horizon_months: int = 360,
    observation_end: int | None = None,
    truth: Truth | None = None,
    term_months: int = 180,
) -> tuple[list[Contract], PathCurve, Truth]:
    """Draw a book, simulate it forward, and return it with its own truth."""
    rng = random.Random(seed)
    truth = truth or Truth()
    curve = PathCurve(path=default_rate_path(horizon_months), slope=0.0015)
    observation_end = (
        horizon_months - 1 if observation_end is None else observation_end
    )

    contracts: list[Contract] = []
    for index in range(n_contracts):
        # Originations spread so that cohorts reach eligibility at different
        # points on the rate path.
        origination = rng.randrange(0, max(1, horizon_months - STATUTORY_LOCKOUT_MONTHS - 12))
        coupon = round(rng.gauss(0.035, 0.006), 6)
        balance = round(rng.lognormvariate(math.log(180_000), 0.45), 2)
        eligible_from = origination + STATUTORY_LOCKOUT_MONTHS
        maturity = origination + term_months

        exit_month: int | None = None
        exit_cause: str | None = None
        burnout_state = 0.0

        for month in range(eligible_from, min(observation_end, maturity - 1) + 1):
            remaining = maturity - month
            incentive_bp = (coupon - curve.refi_rate(month, remaining)) * 10_000.0

            h489 = truth.s489_hazard(incentive_bp, burnout_state)
            draw = rng.random()
            if draw < h489:
                exit_month, exit_cause = month, S489
                break
            if draw < h489 + truth.h_sale:
                exit_month, exit_cause = month, SALE
                break
            if draw < h489 + truth.h_sale + truth.h_default:
                exit_month, exit_cause = month, DEFAULT
                break

            burnout_state += max(incentive_bp, 0.0) / 10_000.0

        if exit_month is None and maturity <= observation_end:
            exit_month, exit_cause = maturity, MATURITY

        contracts.append(
            Contract(
                contract_id=f"C{index:06d}",
                coupon=coupon,
                balance=balance,
                term_months=term_months,
                origination_month=origination,
                eligible_from=eligible_from,
                last_observed=observation_end,
                exit_month=exit_month,
                exit_cause=exit_cause,
                covariates={
                    "size_band": "large" if balance > 200_000 else "small",
                },
            )
        )
    return contracts, curve, truth


__all__ = ["Truth", "generate", "default_rate_path"]
