# Canonicalisation Contract — `dec9-half-even-v1`

**Status:** binding on every checkpoint emitter, both sides. This contract is what
makes two digests comparable (GR-11 rev-2 clause: compute in `double` to match the
source; serialise through rounded decimal to compare). The digest object always
carries `algorithm` and `canonicalisation` (R12).

**Provenance note:** the original contract file was not present in `ocm_v4.4.zip`;
this is a reconstruction by the controller from the constraints stated in the
protocol (R12 evidence list, GR-11 rev-2). Recorded as a bundle finding.

## 1. Scalar rendering

| Value class | Canonical text |
|---|---|
| finite double | 9 significant digits, **round half-even**, format `[-]d.dddddddde±XX` (lowercase `e`, exponent ≥ 2 digits, sign always present) |
| exact zero or negative zero | `0.00000000e+00` |
| NA / NaN (either) | `NA` |
| +Infinity | `INF` |
| −Infinity | `-INF` |
| logical | `true` / `false` / `NA` |
| date | epoch days since 1970-01-01 as decimal integer text; `NA` if missing |
| string / factor label | the UTF-8 text with exactly three escapes: `\` → `\\`, LF → `\n`, CR → `\r`; no trimming, no case folding; missing → `NA` |

Rounding is with respect to the **exact decimal expansion of the IEEE-754 binary
value** (what C `printf %.8e` under glibc/UCRT does, and what Java
`new BigDecimal(double)` + `MathContext(9, HALF_EVEN)` does). `BigDecimal` is
allow-listed for serialisation only (GR-11 gate); it may not appear in a
computation path.

Reference vectors (emitters MUST self-test these at startup):

| double (R literal) | canonical |
|---|---|
| `1` | `1.00000000e+00` |
| `-0.0` | `0.00000000e+00` |
| `2^-13` (= 1.220703125e-4, decimal tie at digit 9) | `1.22070312e-04` |
| `1/3` | `3.33333333e-01` |
| `123456789.5` | `1.23456790e+08` |
| `-2.5e-10` | `-2.50000000e-10` |
| `NaN`, `NA` | `NA` |

## 2. Object serialisation

Kinds: `frame` (named columns, equal length), `series` (one unnamed column, name
`value`), `scalar`, `keyed_list` (string-keyed collection of frames — flattened,
see §4).

**Row order is contractual.** Before serialisation each object is sorted (stable)
by its declared `canonical_order` — an ordered list of `{column, direction}` from
the neutral spec. Comparison: numeric by value, strings bytewise as UTF-8, dates
by epoch day; NA sorts last regardless of direction. Objects whose natural order
is already deterministic declare it anyway.

**Column rendering.** For column `c` with values `v1..vn`:

```
col
<name>
<n>
<canonical(v1)>
...
<canonical(vn)>
```

joined with single `\n` (0x0A), no trailing newline, encoded UTF-8.

**Column digest** = SHA-256 (lowercase hex) of those bytes.

**Object digest** = SHA-256 of:

```
obj
<kind>
<rows>
<cols>
<colname1>=<coldigest1>
...
```

columns in **declared spec order** (not alphabetical), joined with `\n`, UTF-8.

A `scalar` digests as a one-row, one-column frame with column name `value`.

## 3. Digest object (JSON)

```json
{ "algorithm": "SHA-256", "canonicalisation": "dec9-half-even-v1", "value": "<64 hex>" }
```

Never a bare string (R12: two runs whose digests differ but whose
canonicalisation also differs have not been compared at all).

## 4. Keyed lists

`valuation_by_year`-shaped objects are flattened: one checkpoint object per entry,
named `parent[key]`, entries emitted sorted by key (bytewise ascending). A parent
entry of kind `keyed_list` carries `keys` (in full — R3) and an object digest over
`key=<entry object digest>` lines.

## 5. Probes

Each frame carries exactly three probes against the canonically sorted rows:

| selection_rule | row |
|---|---|
| `index:1` | first row |
| `index:ceil(n/2)` | middle row |
| `index:n` | last row |

A probe = `{ "selection_rule": "...", "fields": { "<col>": "<canonical>" } }` over
every column. A probe without its `selection_rule` is invalid (R12).

## 6. Coverage

All five fields always present, `null` when untracked (R12 — an absent field and
a tracked zero are different claims):

```json
{ "row_count": n, "field_count": k, "null_count": m, "min": "<canonical>|null", "max": "<canonical>|null" }
```

`min`/`max` range over every numeric cell of the object; `null` when the object
has no numeric cell. (The five-field set is a controller reconstruction — the
original enumeration was not in the bundle.)

## 7. Inputs binding

Every checkpoint file records, for each input file consumed:
`{ "name", "bytes", "sha256" }`. Two checkpoint files are comparable only if
their input lists agree byte-for-byte.

## 8. Numeric caveat (recorded, not waived)

R accumulates `sum`/`mean`/`var`/`cov` in extended precision (long double) on
glibc; Java `double` accumulation may differ near the 9th significant digit after
catastrophic cancellation. The target emitter therefore uses compensated
(Neumaier) summation in its statistical reductions — an emulation of the source's
accumulator width, not an "improvement" (GR-11). Any residual digest mismatch is
diagnosed by the controller with per-value deltas before it is called a
divergence.
