# A behavioural termination model for §489 BGB

Specification. No code yet, and nothing here is estimated — this document
defines what is to be estimated, from what, and what would make the result
wrong.

## 0. The object

§489 Abs. 1 Nr. 2 BGB gives a borrower on a fixed-rate loan the right to
terminate ten years after full disbursement, on six months' notice, without
compensation. For consumer loans it is mandatory law: it cannot be contracted
away, so every eligible contract in the book carries it whether or not anyone
priced it.

The current model treats exercise as an optimal stopping time,

```
tau = inf { t >= 120 : F_t(remaining term) < K }
```

with `K` the contract coupon and `F_t` the par rate available for the
remaining term at `t`. On the workshop curve that boundary sits at −36 BP.

The proposed model treats `tau` as random and estimates its conditional
intensity,

```
h_t = P( tau = t | tau >= t, F_t, X_t )
```

The threshold does not disappear. It becomes the location parameter of the
incentive variable that drives `h`.

## 1. Exits are not one event

This is the design decision that matters most and the easiest to get wrong.

A contract can leave the book for reasons that have nothing to do with each
other:

| cause | driver | rate-sensitive |
|---|---|---|
| `c1` §489 termination | refinancing incentive | **yes — this is the option** |
| `c2` sale, move, life event | household circumstance | barely |
| `c3` default | credit | weakly, and with opposite sign |
| `c4` scheduled maturity | contract | no |

Fit one hazard to "the contract left" and the estimated incentive slope is
attenuated toward zero, because it is averaged over exits that do not respond
to rates at all. If a share `p` of exits are rate-driven, the pooled slope is
roughly `p * beta_1` rather than `beta_1`.

That attenuation is not a nuisance. **The hedge notional is proportional to
that slope.** An attenuated slope produces a systematically under-sized hedge,
and the error is invisible in-sample because the pooled model fits the pooled
exits perfectly well.

So: **cause-specific hazards**, one per exit reason, estimated jointly.

## 2. The time axis is not loan age

The hazard is identically zero before eligibility, by statute. That is not a
modelling assumption to be tested; it is a constraint to be imposed.

Consequences:

- A contract enters the risk set at eligibility, not at origination. This is
  delayed entry — structural left truncation.
- The baseline hazard is indexed by **time since eligibility**, `s = t − 120`,
  not by loan age. Two contracts originated five years apart are at the same
  baseline point when they are equally far past their tenth anniversary.
- The six-month notice period separates the decision date from the cash-flow
  date. The hazard models the decision; the cash-flow projection shifts it.

Putting all loan-months into the risk set mechanically deflates the hazard and
distorts the baseline shape. It is the same denominator error Efron opens
with: a share of everyone, where a share of the survivors was meant.

## 3. The incentive variable

```
I_it = K_i − F_t( remaining term of contract i )
```

Positive means refinancing is cheaper than staying: the right is in the money.

The comparison is against the **forward par rate for the remaining term seen
from the exercise date**, not the current spot rate for the original term.
That is exactly the derivation the workshop already does for one contract —
coupon 3.2840% against the 10→15 forward at 3.6454%, indifference at −36 BP.
The model generalises that one number to a covariate.

`I` enters non-linearly. The empirical shape in every prepayment literature is
an S-curve: flat while out of the money, steep through the money, saturating
once deep in the money because the remaining non-exercisers are the ones who
were never going to move. Parametrise it transparently — piecewise-linear in
`I` with knots at, say, −100, −50, −25, 0, +25, +50 BP — rather than with a
functional form that hides where the curvature comes from.

## 4. Burnout, and why Efron is not decoration

```
B_it = sum over s < t of max( I_is, 0 )
```

Cumulative time spent in the money without exercising. Given the same current
incentive, a contract with high `B` is less likely to exercise: the ones still
there have already declined the trade repeatedly.

That makes the hazard **decreasing in the surviving population** — which is
precisely Efron's regime for the skewed law of expectation. The longer a
contract has survived a standing incentive, the longer you should expect it to
keep surviving. The link between the survival study and this book is not an
analogy at that point; it is the same monotonicity with the same consequence.

## 5. The estimator

Expand the book into a **contract-month panel**. Contract `i` contributes one
row per month from eligibility until it exits or the observation window ends.

Then fit a multinomial logit over `{survive, c1, c2, c3}`:

```
log( h^c_it / h^0_it ) = alpha^c_s + f^c(I_it) + gamma^c B_it + delta^c' X_it
```

- `alpha^c_s` — baseline by time since eligibility
- `f^c` — the piecewise-linear incentive spline of section 3
- `X_it` — remaining balance, original size, LTV band, contract type, region,
  calendar month for seasonality

Three things this buys:

1. **Censoring is handled by construction.** A contract still running at the
   observation cut simply stops contributing rows. It is neither counted as a
   non-event nor dropped. The person-period expansion *is* the hazard trick,
   in regression form.
2. **Time-varying covariates are natural.** Rates move monthly; the panel
   carries that without special handling.
3. The likelihood factorises over rows, so this is a standard multinomial
   logistic regression and nothing exotic is required to fit it.

Survival follows:

```
S_i(t) = product over s <= t of ( 1 − sum over c of h^c_is )
```

## 6. Validation is by time, and it is not negotiable

Split by calendar date or origination cohort. **Never at random.**

Efron's demonstration is the whole argument: same data, same algorithm, 2%
test error under a random split and 24% under a split by enrolment order. The
model had learned the period, not the mechanism.

Here the leakage is worse than in his case, because every contract alive in a
given month sees the *same* `F_t`. A random split puts the same rate month on
both sides of the partition for thousands of contracts at once.

Stronger still: hold out a **rate regime**, not just a period. A model fitted
only on falling rates has no information about the rising-rate branch of the
S-curve, and will report confident nonsense there.

Score on **calibration**, not ranking alone: predicted against realised exit
counts within incentive buckets. A model that ranks well and is mis-calibrated
produces the wrong cash flows, which is the only output that matters here.

## 7. The measure problem, stated exactly

The fitted `h` is a real-world probability. The €27,645 swaption value is a
risk-neutral price. Then

```
E^P [ sum_t D_t CF_t(tau) ]
```

is **neither quantity**: not the market price, because the measure is wrong;
and not the expected profit and loss, because discounting real-world expected
cash flows at the risk-free curve prices away a risk premium that is actually
borne.

Three defensible routes:

- **(a) Option-adjusted spread.** Project under `P`, discount at risk-free
  plus a spread, calibrate the spread so the model reproduces a reference
  price. Standard practice. Honest but blunt: the spread absorbs the measure
  gap and every model error together, and explains neither.
- **(b) A risk-neutral exercise function.** Re-scale the hazard so model
  prices of traded comparables match market. Needs traded comparables, which
  for Bauspar are scarce.
- **(c) Keep them apart.** Use the `P` hazard for ALM, effective duration and
  cash-flow-at-risk. Use the rational-exercise model for the valuation bound.
  Report both, blend never.

**Recommendation: (c) now, (a) when a reference price exists.** Route (c) is
immediately defensible, and it has a useful structural property: because
§489 is the borrower's right, a borrower who fails to exercise when he should
costs the lender less. So optimal exercise is an upper bound on the option
cost, and the behavioural projection sits below it. Two numbers that bracket
the truth beat one number of unknown measure.

## 8. Outputs

1. **The exercise curve** `h(I)` at mean covariates — the S-curve. This is the
   headline artefact.
2. **Survival curves** by cohort, `S(t)`.
3. **Expected balance profile**, the schedule weighted by survival.
4. **Effective duration and DV01 as expectations**: bump the curve, re-project
   exercise, revalue. There is no closed form once cash flows depend on `tau`.
5. **Diagnostics**: realised against predicted by incentive bucket, by cohort,
   and out of time.

## 9. What would make this wrong

Checked before fitting, not after:

- **No observed §489 exits in the window.** Then nothing is identified. The
  first query against real data must count them, by year.
- **Exit reason not recorded.** Cause-specific estimation becomes impossible,
  the single-risk slope is attenuated per section 1, and the hedge built on it
  is too small. This must be stated as a limitation, not absorbed silently.
- **One rate regime only.** `beta_1` is then not identified out of sample, and
  no amount of in-sample fit reveals it.
- **Bauspar is not a mortgage.** A Bauspar contract carries its own option set
  — allocation timing above all — and §489 reasoning does not transfer to it
  wholesale. Model the two books separately until shown otherwise.
- **Too few eligible contracts.** A thin risk set gives a noisy baseline; pool
  cohorts on a shared `alpha_s` before trusting the shape.

## 10. Status

Nothing in this document has been estimated. It defines the target. The data
questions in section 9 decide what is buildable, and they are asked before any
code is written.
