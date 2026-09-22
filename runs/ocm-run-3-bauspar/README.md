# OCM run 3 — Bauspar customer-lifecycle engine

Governed source-to-target migration under Migration Operating Protocol v4.4 and
General Rules rev 2, using the kit in `ocm-kit/`.

## State reached

| State | Status |
|---|---|
| DISCOVER | **done** — source staged, inventoried, findings F1–F7 recorded |
| PROFILE | **done** — `evidence/input_profile.json`, schema-validated |
| SPECIFY | **done** — gate PASSED, spec releasable to the target room |
| OBSERVE_SOURCE | **done** — `evidence/checkpoints_source.json`, schema-valid, deterministic |
| IMPLEMENT | **done** — TypeScript target built from the spec alone |
| OBSERVE_TARGET | **done** — `evidence/target/checkpoints_target.json`, schema-valid, deterministic |
| COMPARE | **done** — 3 of 3 byte-identical, inputs bound identically, exit 0 |
| VERIFY | **done** — 10 of 12 ladder layers ran (all 9 CORE, plus layer 10) |
| VERDICT | **PROVISIONAL** — `evidence/verdict.json`, schema-valid |

## Verdict: PROVISIONAL

Both halves of that word are load-bearing.

**What was established.** Two implementations — one executing the original in
its own language, one written in TypeScript from a written specification by an
agent that never saw the original — agree on every byte of all three published
objects, over 503 rows, including the browser document's 507 physical lines.
Neither could see the other's values. Ten of twelve ladder layers ran; the two
that did not are FULL-tier and the owner chose CORE.

**Why it is capped.** R2. The real input table is not in the bundle, so every
observation is of a synthetic stand-in. No amount of agreement between the two
sides can lift that, because the layer the record blames for six of ten
historical failures — input shape, layout, encoding and scale — is precisely
the layer this run could not observe at all. GR-09 adds a second cap: nothing
ran at the production scale of 45,881 contracts.

The verdict names both caps, what each absent observation would have covered,
and the six limits, in the artifact rather than in prose.

**What it does not say.** It does not say the unit is correct. Thirteen
catalogued findings describe behaviour that looks wrong — two at FAIL severity
— and under the faithful-only policy all thirteen were reproduced exactly
rather than corrected. FND-02 is the one to escalate: if real tariff values are
percent points rather than fractions, every saving goal in production has been
100× too large for as long as this version has run, and neither side could tell
from this bundle.

### SPECIFY exit gate — controller-executed

Every gate was run by the controller, not accepted from the agent's report.
`evidence/gate_specify_result.json`, exit 0:

| Gate | Result |
|---|---|
| barrier | PASS — spec and flow manifest clean; scanner self-validated on its injected leak (6 patterns) |
| schema | PASS — both artifacts valid |
| R3 | PASS — 7 of 7 declared name vectors agree |

**The R3 gate was run against the controller's own parse, not the agent's.**
The source agent produced its own mechanical parse and ran the gate with it,
which measures the agent's self-consistency — a different and weaker claim than
the one the gate exists to make. The controller re-derived all seven vectors by
a different method (text extraction in Python, against the agent's parse of the
source with R's own parser) and bound the gate to that. Seven agreements
between two unrelated derivations is evidence; an agent agreeing with itself is
not.

Two corrections were made to the controller's own derivation before it could be
trusted, both the controller's bugs rather than spec defects — a sorted vector
that produced a spurious order disagreement, and a regex that missed the amount
markers entirely and reported zero of them. Both would have been reported as
spec defects if left alone.

Fault injection confirms the gate is live rather than vacuous: swapping two
adjacent fields in the record catalogue — the run-2 defect class exactly —
yields `same values, DIFFERENT ORDER` and exit 1.

### OBSERVE_SOURCE

The source agent's emitter was executed by the controller, twice, with the
timestamp fixed: **byte-identical**. Its three digests match what the agent
reported.

| object | kind | rows | cols | canonical order |
|---|---|---|---|---|
| `customer_book` | frame | 503 | 34 | id asc, row_index asc |
| `customer_export_rows` | frame | 503 | 26 | id asc, row_index asc |
| `customers_js_document` | frame | 507 | 2 | line_no asc |

`row_index` is an emitter-added ordering key declared in the spec, so the order
stays total even if contract identifiers repeat (UA-04) — and because it
travels as data, a side that read rows in a different order shows up as a
divergence instead of being hidden by the sort.

The answer key was checked intact after the emitter ran
(`d06cbc27820ad702…`, unchanged), because the emitter executes the unit's
browser-file writer and that writer's default output has the same name.

`evidence/probe_source_execution.json` is a pre-spec **feasibility probe**, not
the run's OBSERVE_SOURCE evidence. It fixes a checkpoint field set and a
canonical row order that the neutral spec is supposed to declare, so calling it
OBSERVE_SOURCE would claim a state the run has not reached. It does establish
the thing that was genuinely in doubt: the engine executes on a stand-in and
emits 33 fields over 503 rows, deterministically (identical digest on re-run).

## Owner decisions — recorded

| Decision | Value |
|---|---|
| Barrier (R21) | structural — source and target agents in separate contexts |
| Inputs | synthetic stand-ins (forced by F1, then chosen) |
| Tier | CORE |
| Target language | TypeScript |
| Findings policy | faithful only — no corrected-behaviour switches |

CORE was chosen knowing F1 already caps the verdict: FULL's extra artifacts
would add evidence about structure, not about reality, and cannot lift a cap
that exists because the inputs are not real.

Faithful-only means the target reproduces the source exactly, including any
behaviour that looks like a defect. Suspected defects are reported as findings
with executable preconditions; none is silently corrected. A divergence is then
unambiguous — there is no legitimate reason for the two sides to differ.

## Source inventory

| File | Bytes | sha256 (first 16) | Role |
|---|---|---|---|
| `customer_engine_v4.R` | 32809 | `5cffb993b00660b0` | the unit under migration |
| `qa_sample_customers_v4.R` | 11051 | `21e77a04dc557c42` | downstream QA harness |
| `customer_view_v4.html` | 14126 | `ae49c266ecb4fcbb` | downstream view |
| `customers_data.js` | 18572560 | `d06cbc27820ad702` | **source OUTPUT — see F2** |

## Findings

### F1 — the source cannot be executed on real data as delivered (caps the verdict, R2)

The engine computes from `merged_data_with_tariff_amount`. Neither that table,
nor the merge, nor the enrichment script that builds it is in the bundle.
`qa_sample_customers_v4.R` states the dependency outright: it `stopifnot`s that
`merged_data_with_tariff_amount` and `compute_contract` already exist in the
session.

Consequence: every observation in this run is made against a synthetic
stand-in, so the verdict is capped under R2 regardless of how well the two
sides agree. That cap must be named in the verdict, not inferred.

### F2 — `customers_data.js` is the source's OUTPUT, not an input (barrier-critical)

Its own header: `generated by customer_engine.R`, `45881 contracts, valuation
date 2026-03-31`. The record count was verified independently: 45,881.

It is the answer key. Under R21 it **must not** reach the target room before
the target has emitted its own checkpoints independently. It is simultaneously
the most valuable artifact in the bundle — a recorded observation of the real
source on real data — and the one that would destroy the run's evidential value
if it crossed early. Handling: it stays in `source_room/` (git-ignored), and
the crossing ledger must show it never crossed.

Note what it cannot do: the year labels it carries (`lab_contract` etc.) are
4-digit years, so exact input dates are not recoverable from it. It cannot be
inverted into the real input table.

### F3 — the input contract is 11 columns, established two independent ways

`BSV, DaBetrag, Tilgungsbeginn, Vertragsende, abschlussdatum,
bausparsumme_teuro, contract_type, einloesungsdatum,
erstmalige_zuteilungsanwartschaft, guthaben, tariff_amount`

The R detector's mechanical column-usage parse and a direct scan of
`contract[[...]]` / `contract$` accesses agree exactly. Recorded as values, not
a count — this is precisely the R3 vector whose absence caused run 2's only
divergence, and it is the vector the spec must state and the gate must check.

### F4 — `input_profile_schema.json` cannot describe a JavaScript-embedded input

Its `kind` enum admits only `delimited_text` and `xlsx` — a run-2 shape. Not
blocking here, because the synthetic input is delimited text, but
`customers_data.js` could not be profiled under this schema if the run ever
wanted to. Recorded rather than silently widened: amending a contract is a
declared step, not a convenience.

### F5 — `system2("sha256sum", input = txt)` in R returns the WRONG digest

It appends a trailing newline, so 41 bytes hash as 42. Verified against an
independent SHA-256 of the same bytes. Digests here go through `writeBin` to a
file, which matches.

This is the dangerous class of defect: a wrong-but-internally-consistent digest
does not crash. It disagrees with the other side on every object and presents
as a real divergence, sending the controller to route a defect that does not
exist. Found only by checking the writer empirically rather than trusting it —
lessons finding 5.

### F6 — R's `sprintf` diverges from the canonicalisation contract on negative zero

`sprintf("%.8e", -0.0)` gives `-0.00000000e+00`; the contract requires
`0.00000000e+00`. Five of the other six reference vectors match exactly,
including the half-even tie at `2^-13`. The emitter special-cases zero and
self-tests all ten vectors at startup, refusing to emit if any fail. The
contract mandates that self-test, and the self-test is what caught this.

### F7 — two defects in the controller's own run-3 tooling, both caught by checking

Recorded because the pattern matters more than the fixes, and because the
controller's tooling is where lessons finding 7 keeps recurring.

1. **A designed branch was not a reached branch.** The stand-in had a row meant
   to drive `savings_ratio` to NA by zeroing the Bausparsumme. It did not:
   DaBetrag remained the reference, so the ratio stayed finite. Invisible until
   the branch tally was actually run against the engine's output. Two rows now
   cover the missing/zero reference paths separately, and the NA path is
   reached twice.

2. **The profiler cried wolf on sound input.** Its first version split lines on
   commas and reported the file as ragged — 11, 14 and 15 fields per line — on
   a file that is exactly rectangular at 11. German decimal-comma amounts are
   CSV-quoted and contain commas. That is lessons finding 7 reappearing inside
   a tool written to enforce the lessons. Field counts now come from a real CSV
   reader, and the naive-split hazard is recorded as a hazard **for the
   target** — any implementation that hand-rolls a delimiter split will
   mis-assign every column after the first amount, silently.

## Barrier state (R21)

Nothing has crossed. No agent has been spawned. The target room does not exist
yet. `source_room/` is git-ignored and holds the source, the answer key
(`customers_data.js`) and the generated stand-in.

## Reproducing

```sh
python3 runs/ocm-run-3-bauspar/tools/gen_synthetic_bauspar.py \
    --out-dir source_room/inputs
python3 runs/ocm-run-3-bauspar/tools/profile_inputs_bauspar.py
Rscript  runs/ocm-run-3-bauspar/tools/observe_source.R
```

The generator is seeded and clock-free, so the CSV and the probe digest
(`82bf5ab2...`) reproduce byte for byte. The synthetic data itself is not
committed: it is fully determined by the generator, and committing generated
data invites someone to edit the data instead of the generator.

### F8 — the spec schema polices provenance in one place and not the other

`neutral_spec_schema.json` constrains `provenance` to the four-value enum only
under `io_formats[].expectations[]`. The same key also appears 31 times under
`units[].constants[]`, where the schema constrains nothing, and a different
vocabulary is in use there: `source_declared` 30 times and a bare `observed`
once.

The 17 constrained tags are honest — 8 `observed_in_synthetic_input`, 6
`source_code_declared`, 3 `assumption`, and no `observed_in_real_input`
anywhere, which is correct because no real input exists.

The single bare `observed` is on `round_reference_vectors`, sixteen measured
cases of the source language's rounding. That is observed by executing the
platform, not by reading an input, so neither `observed_in_real_input` nor
`observed_in_synthetic_input` would be truthful. The tag is honest and the
vocabulary is missing — which is the point.

Not blocking, and not amended mid-run: lesson 3's fix was to stop a synthetic
observation from wearing a real observation's label, and the location where
that could happen **is** constrained. But an unconstrained provenance field is
the door that defect walks back through, and a fifth term is needed for facts
observed from the runtime rather than from data. Recorded for v4.5 alongside
F4.

### F9 — the abort is position-dependent, not value-dependent (corrects FND-06)

FND-06 records that the date reader aborts on a malformed hyphenated value and
silently accepts a malformed digit value. True, but incomplete in a way that
matters: the abort depends on **where the value sits**, not on the value.

The source language's date conversion infers a format from the first non-NA
element of the vector it receives and then applies it to the rest. Measured:

| call | result |
|---|---|
| a single bad hyphenated value | abort |
| good value first, bad second | no abort — bad value silently missing |
| bad value first, good second | abort |
| missing, then bad, then good | abort — a leading missing is not "the first element" |

Because the unit computes one contract at a time, a column the unit parses
itself always presents its value as the first element, so every bad hyphenated
value in such a column aborts. A column the harness coerces to a date type
beforehand is converted all at once, so only a bad value in the first
non-missing position aborts.

Which columns get coerced is a declared setting in the stand-in's manifest.
That setting therefore changes whether the abort fires at all, which makes it
part of the observation contract rather than an incidental staging detail.

This was caught because the first abort probe placed the bad value in a
harness-coerced column and **did not abort** — the branch the probe existed to
exercise was not reached. The same class of miss as F7's unreached branch, and
the reason Rule E of controller directive 01 requires the path to be exercised
rather than merely specified. Had the first draft shipped, the target would
have been handed a rule stating the abort depends on the value, and a
divergence on the abort path would have been routed as a target defect when it
was the controller's directive that was wrong.

Controller directive 01 (`controller_directive_01_abort.md`) carries the
corrected trigger and binds both sides.

## IMPLEMENT / OBSERVE_TARGET / COMPARE

The target was built in a separate context from the neutral spec alone, in
TypeScript, zero runtime dependencies.

### Barrier — checked, not accepted

The target agent's report lists what it read. The controller checked what can
be checked independently:

- `find target_room -name '*.[Rr]'` → 0 files.
- Barrier scan of all 21 TypeScript/mjs modules → CLEAN, 0 hits, scanner
  self-validated on its injected leak.
- The three source digests appear nowhere in the target's sources (`grep` over
  `src/` and `tools/` → 0 hits), so they are computed, not transcribed.
- The controller deleted `dist/`, rebuilt from source, and re-ran the program
  itself. All three digests reproduced exactly.

That last check is the one that matters: a target that had seen the answers
could hard-code them, but not recompute them from its own sources after a
clean rebuild.

### COMPARE — 3 of 3 digests byte-identical

| object | rows | cols | digest | |
|---|---|---|---|---|
| `customer_book` | 503 | 34 | `9ef73ff0…0db90b` | AGREE |
| `customer_export_rows` | 503 | 26 | `afa5ebd0…996f81` | AGREE |
| `customers_js_document` | 507 | 2 | `fc9c29b4…c20e506a` | AGREE |

Two independently written implementations, in different languages, in
separate contexts, neither able to see the other's values, agreeing on every
byte of all three published objects — including the browser document's 507
physical lines, which exercises the value rendering, the identifier escaping
and the second rounding rule that the two frames cannot reach.

### …and the comparison is NOT YET VALID

`inputs bound identically: False`. The canonicalisation contract §7 makes two
checkpoint files comparable only if their input lists agree, and they do not:
the source declares one input, the target declares two.

The target is right. The source emitter reads the stand-in manifest
(`readLines` at line 215) and takes two decisive settings from it — the harness
date-class coercions and the valuation date — but does not list it. An
under-reported consumed input is the silent decline R16 forbids.

Routed to the source agent as an emitter defect. The controller did not fix it:
a divergence is routed to the responsible side, never resolved by the
controller copying something across. The object digests are unaffected, since
the inputs list is provenance metadata and not part of any object digest —
stated to the source agent as a constraint on the fix, so a changed digest
would itself be a finding.

### F10 — COMPARE reported a disqualifying condition and exited 0 anyway

`compare_checkpoints.py` had no `sys.exit` at all. It returned 0 whatever it
found: a real divergence, an object present on only one side, or input lists
that §7 says make the two files incomparable. It printed
`inputs bound identically: False` and then exited 0.

A controller scripting the gate would have read success. This is the same shape
as the R3 gate that agreed having compared nothing (F/lessons 10), in the tool
that produces the run's central evidence.

Given the three-valued contract now used by every other gate: 0 comparable and
agreeing, 1 comparable and diverging, 2 not comparable. Three tests pin it,
including the case that matters — agreeing digests over differing input lists
return 2, because agreement over different inputs establishes nothing.
