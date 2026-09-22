# Where the spec under-determined the behaviour — target_java's readings

Every place this agent had to CHOOSE. These are the places the spec does not pin the
source down, and each is a candidate divergence with the other target. Listed with the
reading taken and why.

## A. Coverage and probe conventions (canonicalisation contract, sections 5 and 6)

**A1. `field_count` in `coverage`.** The contract gives the five names and no definition.
Read as **the number of columns** (34 / 26 / 2), not the number of cells. "Field" reads
more naturally as a column than as a cell, and `row_count` already carries the other
dimension.

**A2. Does the emitter-added index column count as a numeric cell for `min`/`max`?**
The contract says min/max "range over every numeric cell of the object". `row_index` and
`line_no` ARE numeric cells of the object as declared, so they are **included**. On this
input it changes nothing for the two frames (their true extremes are far outside 1..503)
but it wholly determines `customers_js_document`'s min/max, which are `1` and `507`.
If the other side excluded them, that object's coverage differs while its digest agrees.

**A3. `null_count`.** Read as **the count of cells whose canonical text is `NA`**, over
every column. An empty text is a value, not a null, so the 83 empty `contract_type` values
and the empty year labels do not count.

**A4. `min`/`max` over non-finite values.** NaN cannot be an extreme; read as **over the
finite numeric cells**, with `null` when there is none.

**A5. `selection_rule` text.** Emitted as the contract prints it — the literal strings
`index:1`, `index:ceil(n/2)`, `index:n` — not resolved to `index:252`. A literal rule is
reproducible on the other side, which is what R12 asks of it. `ceil(n/2)` for n=503 is
row 252; for n=507 it is row 254.

## B. The harness date coercion

**B1. What the coercion does, mechanically.** The manifest DECLARES which columns are
coerced; it does not say how. Controller directive 01 says the conversion "infers a format
from the first non-NA element of the vector it is given, then applies that format to the
rest". Read as: trim, apply the seven missing markers, take the first remaining element,
try year-month-day with hyphens then with slashes, **abort if neither works**, then apply
the winning format to the whole column with non-matching values going silently missing.

**B2. What counts as "missing" for the purpose of finding that first element.** Read as
**the same seven markers the unit uses**, because the directive states the trigger as
"after trimming and after the seven missing-markers are applied".

**B3. It makes no difference on either staged file.** In `merged_data_synthetic.csv` both
coerced columns hold hyphenated dates plus markers only, so coercion and the unit's own
C1 branch agree value for value. The reading is therefore **untested by the data**: it
would only show up on a coerced column holding eight-digit text, which neither file has.

## C. Which date fields the record publishes

**C1. `contract_start_date`, `allocation_date`, `contract_end_date` are published AFTER
their fallbacks (C4, C5, C6), not as read.** C5 says "the contract start date **as it
stands after step C4**", which only makes sense if C4 overwrites the variable; FND-08 says
a contract with neither date recorded is published "in the done phase, **with the milestone
years shown**", which requires the fallback dates to reach the year labels.

**C2. `first_payment_date` and `loan_start_date` are published as read** and may be
missing. `loan_start_date` is the **repayment start** (`Tilgungsbeginn`): C18 lists the
four year labels as contract start, first payment, allocation and **repayment start**, and
the fourth is named `year_loan_start`.

## D. Rounding and arithmetic

**D1. The positional constants are written as the spec declares them** (0.6, 0.34, 0.46),
not re-derived at run time. Checked: `1-0.4`, `0.4-0.06` and `0.4+0.06` are bit-identical
to the literals `0.6`, `0.34` and `0.46`, so the choice is unobservable.

**D2. Rounding is applied to every one of the fourteen fields including the three constant
positions** (`x_contract` 0.02, `x_first_payment` 0.06, `x_allocation` 0.4). C19 says the
fourteen named in `rounding_places` are rounded, and those three are among them. Rounding
them changes nothing, but it is what the spec says.

**D3. `x_loan_start` is rounded like the rest**; when it is missing, C20 returns the
missing value unchanged.

## E. The unit's entry points this target does and does not implement

**E1. C24's progress indicator, C26's single-contract inspector and C27's standalone-page
writer are NOT built.** CORE tier stands down the UI (directive 6/7), and none of them
feeds a checkpoint object. Consequence: **FND-07 is unobservable in this bundle** — the
finding that the standalone-page writer ignores its own table argument cannot be exercised.
That is stated, not silently skipped.

**E2. The load-time three-way branch (L2) is not reproduced.** This target is an observer
harness, not a session; it takes branch (c)'s position — nothing is computed at load — and
then invokes the whole-book calculation explicitly. The valuation date therefore comes from
the manifest or the command line, never from a session value named `VAL_DATE` and never
from the unit's own 2026-03-31 default. P-12 records which applied.

## F. Where the spec's io_formats claims and this target's reading DIFFER

Two of twenty-eight expectations differ, both distributional, both about a generated
stand-in, and both reconciled from the data:

| expectation | spec reads | we read | reconciliation |
|---|---|---|---|
| `DaBetrag` values MISSING once read | 2 | **1** | missing 1 + zero-valued 1 = 2 |
| `bausparsumme_teuro` values MISSING once read | 3 | **0** | missing 0 + zero-valued 3 = 3 |
| `guthaben` values MISSING once read | 0 | 0 | missing 0 + zero-valued 0 = 0 |

All three reconcile exactly if the spec's counts are **missing-or-zero** rather than
missing. That is a derived explanation, not a guess: the same rule fits all three fields
including the one that agrees. The counts are `observed_in_synthetic_input`, the manifest
forbids hardening them into a target-enforced contract, and nothing the computation
depends on differs — so the run **continued and reported both readings** rather than
halting. Halting there would have been the bill-of-materials failure the directives warn
about twice.

## G. Not verified, and not verifiable from here

- The real contract table is absent. Every input fact came from a generated stand-in;
  under R2 the verdict is capped at PROVISIONAL however well the two sides agree.
- No source-side value was seen, by construction (R21).
- FND-03 and FND-04 pass **vacuously**: no identifier repeats and none arrives numeric.
- Three of the seven date missing-markers (`00`, `0000`, `<NA>`) never occur in either
  staged file; they are covered only by the unit tests.
- Every threshold in this build has only ever seen synthetic data (R15).
