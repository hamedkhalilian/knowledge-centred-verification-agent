"""Contract records and the rate source the incentive is measured against."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# Cause-specific exits. Only S489 is the rate-driven option; pooling it with
# the others attenuates the incentive slope, and the hedge notional is
# proportional to that slope. See docs/TERMINATION_MODEL.md section 1.
S489 = "s489"
SALE = "sale"
DEFAULT = "default"
MATURITY = "maturity"

EXIT_CAUSES = (S489, SALE, DEFAULT, MATURITY)

#: Causes whose hazard is worth modelling. Maturity is deterministic: it
#: happens when the schedule says so and carries no behaviour.
MODELLED_CAUSES = (S489, SALE, DEFAULT)

ExitCause = str

#: §489 Abs. 1 Nr. 2 BGB: the right arises ten years after full disbursement,
#: on six months' notice. The decision and the cash flow are therefore two
#: different dates, and only the first is what the hazard models.
STATUTORY_LOCKOUT_MONTHS = 120
STATUTORY_NOTICE_MONTHS = 6


class TermCurve(Protocol):
    """Supplies the rate a borrower could refinance into.

    The comparison that matters is against the par rate for the *remaining*
    term seen from the exercise date, not the spot rate for the original term.
    That is the generalisation of the workshop's single-contract derivation.
    """

    def refi_rate(self, month: int, remaining_months: int) -> float:
        """Annual par rate, as a decimal, for ``remaining_months`` at ``month``."""


@dataclass(frozen=True)
class FlatCurve:
    """A constant curve. For tests and for sanity checks, not for a real book."""

    rate: float

    def refi_rate(self, month: int, remaining_months: int) -> float:
        return self.rate


@dataclass(frozen=True)
class PathCurve:
    """A realised rate path with an optional term spread.

    ``path[m]`` is the short-to-medium par level in month ``m``; ``slope`` adds
    a linear term premium per year of remaining maturity, which is crude but
    explicit. A production run should replace this with the bootstrapped
    forward par rate for the remaining term.
    """

    path: tuple[float, ...]
    slope: float = 0.0

    def refi_rate(self, month: int, remaining_months: int) -> float:
        if not self.path:
            raise ValueError("PathCurve requires at least one rate")
        level = self.path[min(month, len(self.path) - 1)]
        return level + self.slope * (remaining_months / 12.0)


@dataclass
class Contract:
    """One loan, in month indices on a shared calendar.

    ``eligible_from`` is when §489 becomes exercisable. It is stored rather
    than derived so that a book with non-standard disbursement dates, or a
    product where the right arises differently, needs no special casing.

    ``exit_month`` is the month the exit is *decided*. A contract still
    running at ``last_observed`` is right-censored: it contributes exposure up
    to that month and no event. That is the whole censoring treatment, and it
    is why no contract is ever dropped for having an unknown fate.
    """

    contract_id: str
    coupon: float
    balance: float
    term_months: int
    origination_month: int
    eligible_from: int
    last_observed: int
    exit_month: int | None = None
    exit_cause: ExitCause | None = None
    covariates: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.exit_month is None and self.exit_cause is not None:
            raise ValueError(
                f"{self.contract_id}: exit_cause without exit_month"
            )
        if self.exit_month is not None and self.exit_cause is None:
            raise ValueError(
                f"{self.contract_id}: exit_month without exit_cause; an exit of "
                "unknown cause must be recorded as such, not left blank"
            )
        if self.exit_cause is not None and self.exit_cause not in EXIT_CAUSES:
            raise ValueError(
                f"{self.contract_id}: unknown exit cause {self.exit_cause!r}"
            )

    @property
    def maturity_month(self) -> int:
        return self.origination_month + self.term_months

    def remaining_months(self, month: int) -> int:
        return max(0, self.maturity_month - month)

    def observed_until(self) -> int:
        """Last month this contract contributes exposure."""
        if self.exit_month is not None:
            return min(self.exit_month, self.last_observed)
        return self.last_observed


def default_eligibility(origination_month: int) -> int:
    """Eligibility under the statutory lockout, decision date not cash date."""
    return origination_month + STATUTORY_LOCKOUT_MONTHS


__all__ = [
    "Contract",
    "ExitCause",
    "FlatCurve",
    "PathCurve",
    "TermCurve",
    "S489",
    "SALE",
    "DEFAULT",
    "MATURITY",
    "EXIT_CAUSES",
    "MODELLED_CAUSES",
    "STATUTORY_LOCKOUT_MONTHS",
    "STATUTORY_NOTICE_MONTHS",
    "default_eligibility",
]
