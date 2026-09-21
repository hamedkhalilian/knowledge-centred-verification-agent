"""Tests for the §489 termination model.

The load-bearing one is `test_the_pipeline_recovers_a_known_curve`: a book is
generated from a curve that is known exactly, and the measured curve has to
come back. Verification by inversion, the same discipline the migration
protocol uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from termination.curve import (
    annualise,
    empirical_exercise_curve,
    survival,
    wilson_interval,
)
from termination.load import read_contracts, read_rates, write_contracts
from termination.model import (
    DEFAULT,
    MATURITY,
    S489,
    SALE,
    STATUTORY_LOCKOUT_MONTHS,
    Contract,
    FlatCurve,
    PathCurve,
    default_eligibility,
)
from termination.panel import (
    DEFAULT_INCENTIVE_EDGES_BP,
    bucket,
    bucket_label,
    build_panel,
)
from termination.synth import Truth, default_rate_path, generate
from termination.validation import random_calibration, temporal_calibration


def make_contract(**overrides) -> Contract:
    base = dict(
        contract_id="C1",
        coupon=0.04,
        balance=200_000.0,
        term_months=180,
        origination_month=0,
        eligible_from=STATUTORY_LOCKOUT_MONTHS,
        last_observed=179,
    )
    base.update(overrides)
    return Contract(**base)


# --- contract invariants ------------------------------------------------


def test_exit_month_without_cause_is_rejected() -> None:
    """An exit of unknown cause must be recorded, never left blank.

    Treating it as censoring would understate every hazard.
    """
    with pytest.raises(ValueError, match="exit_month without exit_cause"):
        make_contract(exit_month=130)


def test_exit_cause_without_month_is_rejected() -> None:
    with pytest.raises(ValueError, match="exit_cause without exit_month"):
        make_contract(exit_cause=S489)


def test_unknown_cause_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown exit cause"):
        make_contract(exit_month=130, exit_cause="vibes")


def test_default_eligibility_is_the_statutory_lockout() -> None:
    assert default_eligibility(24) == 24 + STATUTORY_LOCKOUT_MONTHS


# --- bucketing ----------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    # bucket counts the edges at or below the value, so an exact edge opens
    # the bin above it: 0.0 lands in [0, 25) and -0.001 in [-25, 0).
    [(-1000.0, 0), (-200.0, 1), (-199.0, 1), (0.0, 7), (-0.001, 6), (10_000.0, 13)],
)
def test_bucket_edges(value: float, expected: int) -> None:
    assert bucket(value, DEFAULT_INCENTIVE_EDGES_BP) == expected


@pytest.mark.parametrize(
    "value,expected_label",
    [(0.0, "[0, 25)bp"), (-0.001, "[-25, 0)bp"), (-1000.0, "< -200bp"),
     (10_000.0, ">= 200bp")],
)
def test_bucket_label_matches_the_bin_the_value_falls_in(
    value: float, expected_label: str
) -> None:
    index = bucket(value, DEFAULT_INCENTIVE_EDGES_BP)
    assert bucket_label(index, DEFAULT_INCENTIVE_EDGES_BP) == expected_label


def test_bucket_labels_name_the_open_tails() -> None:
    assert bucket_label(0, DEFAULT_INCENTIVE_EDGES_BP).startswith("<")
    assert bucket_label(13, DEFAULT_INCENTIVE_EDGES_BP).startswith(">=")


# --- panel construction -------------------------------------------------


def test_no_exposure_before_eligibility() -> None:
    """The hazard is zero before the tenth anniversary by statute.

    That is a constraint to impose, not an assumption to test, so those
    months must never enter the risk set.
    """
    contract = make_contract()
    panel = build_panel([contract], FlatCurve(0.04))
    assert panel.exposure == 180 - STATUTORY_LOCKOUT_MONTHS


def test_a_contract_that_never_becomes_eligible_is_counted_not_dropped() -> None:
    contract = make_contract(last_observed=60)
    panel = build_panel([contract], FlatCurve(0.04))
    assert panel.exposure == 0
    assert panel.contracts_never_eligible == 1


def test_a_censored_contract_contributes_exposure_and_no_event() -> None:
    contract = make_contract(last_observed=150)
    panel = build_panel([contract], FlatCurve(0.04))
    assert panel.exposure == 150 - STATUTORY_LOCKOUT_MONTHS + 1
    assert panel.event_totals() == {}


def test_maturity_is_censoring_not_an_event() -> None:
    """Reaching the end of the schedule is not a behaviour."""
    contract = make_contract(exit_month=180, exit_cause=MATURITY)
    panel = build_panel([contract], FlatCurve(0.04))
    assert panel.exposure > 0
    assert panel.event_totals() == {}


def test_an_exit_is_recorded_in_the_month_it_is_decided() -> None:
    contract = make_contract(exit_month=130, exit_cause=S489)
    panel = build_panel([contract], FlatCurve(0.04))
    assert panel.event_totals() == {S489: 1}
    assert panel.exposure == 130 - STATUTORY_LOCKOUT_MONTHS + 1


def test_causes_stay_separate() -> None:
    contracts = [
        make_contract(contract_id="A", exit_month=130, exit_cause=S489),
        make_contract(contract_id="B", exit_month=132, exit_cause=SALE),
        make_contract(contract_id="C", exit_month=134, exit_cause=DEFAULT),
    ]
    totals = build_panel(contracts, FlatCurve(0.04)).event_totals()
    assert totals == {S489: 1, SALE: 1, DEFAULT: 1}


def test_incentive_sign_follows_the_coupon_against_the_refinancing_rate() -> None:
    cheap = build_panel([make_contract(coupon=0.05)], FlatCurve(0.03))
    dear = build_panel([make_contract(coupon=0.02)], FlatCurve(0.03))
    assert all(c.mean_incentive_bp > 0 for c in cheap.cells.values())
    assert all(c.mean_incentive_bp < 0 for c in dear.cells.values())


def test_calendar_window_restricts_exposure() -> None:
    contract = make_contract()
    full = build_panel([contract], FlatCurve(0.04)).exposure
    early = build_panel([contract], FlatCurve(0.04), max_month=140).exposure
    late = build_panel([contract], FlatCurve(0.04), min_month=141).exposure
    assert early + late == full


def test_strata_split_cells() -> None:
    contracts = [
        make_contract(contract_id="A", covariates={"band": "x"}),
        make_contract(contract_id="B", covariates={"band": "y"}),
    ]
    panel = build_panel(contracts, FlatCurve(0.04), strata_keys=("band",))
    assert len({cell.key.strata for cell in panel.cells.values()}) == 2


# --- the curve ----------------------------------------------------------


def test_wilson_interval_brackets_the_estimate() -> None:
    low, high = wilson_interval(5, 100)
    assert low < 0.05 < high
    assert low > 0.0


def test_wilson_interval_stays_in_range_at_zero_events() -> None:
    low, high = wilson_interval(0, 50)
    assert low == 0.0
    assert 0.0 < high < 1.0


def test_wilson_interval_of_an_empty_cell_is_degenerate() -> None:
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_annualise_matches_the_compounding_identity() -> None:
    assert annualise(0.0) == 0.0
    assert annualise(0.01) == pytest.approx(1 - 0.99 ** 12)


def test_survival_is_the_running_product() -> None:
    assert survival([0.1, 0.1]) == pytest.approx([0.9, 0.81])


def test_monotonicity_violations_are_reported_not_smoothed() -> None:
    contracts, curve, _ = generate(n_contracts=400, seed=3)
    exercise = empirical_exercise_curve(build_panel(contracts, curve))
    # The property under test is that the check runs and returns pairs; a
    # thin synthetic book will usually have at least one noisy inversion.
    assert isinstance(exercise.monotonicity_violations(), list)


def test_the_curve_rises_with_the_incentive() -> None:
    contracts, curve, _ = generate(n_contracts=6000)
    points = [
        p
        for p in empirical_exercise_curve(build_panel(contracts, curve)).points
        if p.exposure >= 5_000
    ]
    deep_out = min(points, key=lambda p: p.mean_incentive_bp)
    deep_in = max(points, key=lambda p: p.mean_incentive_bp)
    assert deep_in.hazard > 5 * deep_out.hazard


# --- recovery: the load-bearing test ------------------------------------


@pytest.mark.parametrize("seed", [20260921, 7, 99, 1234])
def test_the_pipeline_recovers_a_known_curve(seed: int) -> None:
    """Expected events under the generating truth must match observed ones.

    Compared against the truth integrated over the contract-months actually
    at risk, not against the truth at a bin's mean incentive: the latter
    confounds a real error with the curvature of the hazard inside the bin.
    """
    contracts, curve, truth = generate(n_contracts=6000, seed=seed)
    expected = 0.0
    for contract in contracts:
        burnout = 0.0
        start = max(contract.eligible_from, contract.origination_month)
        for month in range(start, contract.observed_until() + 1):
            remaining = contract.remaining_months(month)
            if remaining <= 0:
                break
            incentive = (
                contract.coupon - curve.refi_rate(month, remaining)
            ) * 10_000.0
            expected += truth.s489_hazard(incentive, burnout)
            burnout += max(incentive, 0.0) / 10_000.0

    observed = build_panel(contracts, curve).event_totals().get(S489, 0)
    assert observed / expected == pytest.approx(1.0, abs=0.05)


def test_burnout_suppresses_exercise() -> None:
    """A positive burnout coefficient must reduce §489 exits, all else equal."""
    plain, _, _ = generate(n_contracts=3000, seed=11, truth=Truth())
    burnt, _, _ = generate(
        n_contracts=3000, seed=11, truth=Truth(burnout=0.35)
    )
    count = lambda book: sum(1 for c in book if c.exit_cause == S489)
    assert count(burnt) < count(plain)


def test_the_rate_path_visits_both_branches() -> None:
    path = default_rate_path(360)
    assert min(path) < 0.025 < max(path)


# --- validation ---------------------------------------------------------


def test_temporal_split_exposes_unseen_bins() -> None:
    """A regime the training window never saw must be named, not imputed."""
    contracts, curve, _ = generate(n_contracts=6000)
    calibration = temporal_calibration(contracts, curve, split_month=240)
    assert calibration.unseen_exposure > 0
    assert any(b.unseen for b in calibration.bins)
    for b in calibration.bins:
        if b.unseen:
            assert b.predicted == 0.0


def test_leverage_flags_a_thin_training_cell() -> None:
    contracts, curve, _ = generate(n_contracts=6000)
    calibration = temporal_calibration(contracts, curve, split_month=240)
    stretched = [b for b in calibration.bins if not b.unseen and b.leverage > 10]
    assert stretched, "expected at least one heavily extrapolated bin"


def test_random_split_flatters_relative_to_a_regime_change() -> None:
    """The gap between the two splits is the point of running both."""
    contracts, curve, _ = generate(n_contracts=6000)
    chance = random_calibration(contracts, curve)
    temporal = temporal_calibration(contracts, curve, split_month=240)
    assert chance.absolute_error < temporal.absolute_error


def test_random_split_halves_are_disjoint_and_complete() -> None:
    contracts, curve, _ = generate(n_contracts=1500, seed=5)
    chance = random_calibration(contracts, curve)
    whole = build_panel(contracts, curve).exposure
    train_exposure = sum(b.train_exposure for b in chance.bins)
    test_exposure = sum(b.exposure for b in chance.bins)
    assert train_exposure + test_exposure == whole


# --- CSV round trip -----------------------------------------------------


def test_contracts_round_trip_through_csv(tmp_path: Path) -> None:
    original, _, _ = generate(n_contracts=200, seed=42)
    path = tmp_path / "contracts.csv"
    write_contracts(original, path)
    restored = read_contracts(path)
    assert len(restored) == len(original)
    assert restored[0].contract_id == original[0].contract_id
    assert restored[0].exit_cause == original[0].exit_cause
    assert restored[0].covariates == original[0].covariates


def test_a_bad_contract_row_names_its_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "contract_id,coupon,balance,term_months,origination_month,"
        "eligible_from,last_observed,exit_month,exit_cause\n"
        "C1,not-a-number,1,180,0,120,179,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="line 2"):
        read_contracts(path)


def test_rates_carry_forward_across_gaps(tmp_path: Path) -> None:
    path = tmp_path / "rates.csv"
    path.write_text("month,rate\n0,0.04\n3,0.02\n", encoding="utf-8")
    curve = read_rates(path)
    assert curve.refi_rate(1, 60) == pytest.approx(0.04)
    assert curve.refi_rate(3, 60) == pytest.approx(0.02)


def test_rates_starting_after_month_zero_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "rates.csv"
    path.write_text("month,rate\n5,0.04\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must cover month 0"):
        read_rates(path)


def test_term_slope_raises_the_refinancing_rate_with_maturity() -> None:
    curve = PathCurve(path=(0.03,), slope=0.002)
    assert curve.refi_rate(0, 120) > curve.refi_rate(0, 12)
