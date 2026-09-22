# Controller directive 01 — the abort path (FND-06)

**Status:** binding on both sides for run 3. Issued at SPECIFY exit, before
IMPLEMENT, so neither side meets it for the first time during OBSERVE.
**Authority:** controller. This is a contract amendment, not a spec change: it
says what the two sides must EMIT when the source's own abort fires. It does
not alter what the source does, and the faithful-only findings policy is
unchanged.

## Why a rule is needed

The unit's date reader fails asymmetrically. A value containing a hyphen that
cannot be parsed raises an error that propagates out of the whole run; a value
without a hyphen that cannot be parsed becomes missing, silently.

Measured on the unit itself:

| input | behaviour |
|---|---|
| `2013-13-45` | **abort** — "character string is not in a standard unambiguous format" |
| `not-a-date` | **abort** — same |
| `2011/04/01` | silent missing (no hyphen, so it takes the digit branch) |
| `abcdefgh` | silent missing |
| `20131345` | silent missing |
| `2013112` | **silently reads as 2013-11-02** — seven digits, not width-checked |

Without a rule, one side could abort where the other completes, and COMPARE
would have no basis on which to call that agreement or divergence. That is not
a hypothetical: the target is a different language whose date parser will not
fail on the same inputs unless it is told to.

## The trigger, stated mechanically — CORRECTED

The first draft of this directive said the abort depends on the offending
value. **It does not, and getting this wrong would have put a false rule into
the target's hands.** It depends on the value's POSITION.

The source language's date conversion infers a format from the **first non-NA
element** of the vector it is given, then applies that format to the rest.
Measured:

| call | result |
|---|---|
| a single bad hyphenated value | **abort** |
| good value first, bad value second | `2010-01-01, NA` — **no abort**, bad value silently missing |
| bad value first, good value second | **abort** |
| missing first, then bad, then good | **abort** — a leading missing does not count as the first element |

So the same text aborts or goes quietly missing depending only on what sits
before it.

This interacts with how each column reaches the reader, and the two paths
behave differently:

1. **Columns the unit parses itself.** The unit computes one contract at a
   time and hands the reader a single value, so that value is always the first
   element. Every hyphenated unparseable value in such a column aborts,
   whatever row it is in. Verified: a bad value in row 3 of an engine-parsed
   column aborts at `row_index` 3 after 2 completed rows.

2. **Columns the harness coerces to a date type before the unit sees them.**
   The coercion converts the whole column at once, so only a bad value in the
   FIRST non-missing position aborts; anywhere else it becomes missing and the
   run completes. Verified: the same bad value placed in a harness-coerced
   column produced no abort at all.

**Consequence the target must be told:** which columns the harness coerces is
a declared setting in the stand-in's manifest, and that setting changes whether
the abort fires. It is therefore part of the observation contract, not an
incidental detail of the staging. Both sides apply the same declared coercions
to the same columns, and neither side may infer them.

The trigger, then: a date field's text -- after trimming and after the seven
missing-markers are applied -- **contains a hyphen**, is not accepted by the
standard unambiguous parse, AND is the first non-missing element of the vector
the conversion is applied to. Text without a hyphen never aborts, whatever it
contains. The target must NOT validate the digit branch more strictly, and
must NOT make the hyphen branch more forgiving.

## Rule A — both sides abort, at the same place

On the trigger, each side stops processing immediately. Neither side skips the
row, substitutes a missing value, or continues to the next contract.

## Rule B — an aborted run emits NO checkpoint file

A partial checkpoint is not comparable (R12): two partial files that stop at
different rows would digest differently for a reason that has nothing to do
with the behaviour under test, and two that stop at the same row would agree
while saying nothing about the rows never reached. So the emitter writes no
`checkpoints_*.json` at all.

## Rule C — an aborted run emits `abort_record.json` instead

Both sides emit a file with exactly these fields, and COMPARE compares these
instead of digests:

| field | meaning |
|---|---|
| `run_id`, `side`, `state` | as in a checkpoint file |
| `unit` | the unit that aborted |
| `abort_code` | fixed string `DATE_PARSE_ABORT` |
| `row_index` | 1-based position of the offending row in the input table **as received**, before any sort |
| `column` | the input column whose value triggered it |
| `raw_value` | the offending text, rendered by the canonicalisation contract's string rule |
| `rows_completed` | how many rows finished before the abort |

`row_index` is the same emitter-added key the checkpoint objects carry, so the
two artifacts speak the same coordinate system.

## Rule D — what COMPARE does

1. Both sides aborted, and `abort_code`, `row_index`, `column` and `raw_value`
   all match → **agreement on the abort path**. `rows_completed` must match
   too; if it does not, the sides disagree about how far they got and that is
   a divergence.
2. One side aborted, the other completed → **divergence**, routed as a target
   defect unless the spec is shown to under-determine the trigger, in which
   case it is a spec defect and the source agent amends.
3. Both aborted at different rows or on different values → **divergence**,
   diagnosed from the two abort records alone before anything else is shared.

## Rule E — this path is exercised, not merely specified

A branch that is specified but never reached is an untested branch that still
gets migrated. This run has already had one such case, where a stand-in row
designed to drive a value missing did not reach the branch at all and the gap
was invisible until the outcome was tallied.

So the abort path gets its own probe input, `inputs/abort_probe.csv`, one row
of which carries a hyphenated unparseable date, placed in a column the unit
parses itself rather than one the harness coerces -- because, per the corrected
trigger above, a bad value in a coerced column would NOT abort and the probe
would silently prove nothing. Verified to abort at row_index 3 after 2
completed rows. It is a SEPARATE file from the
main stand-in on purpose: the trigger halts the whole run, so a poisoned row in
the main table would make ordinary OBSERVE impossible.

Both sides run the probe as a second, smaller observation and emit
`abort_record.json` from it. The main stand-in must remain abort-free, and the
controller verifies that it is.

## What this directive does NOT decide

It does not say the abort is correct behaviour. FND-06 stands as a FLAGGED
finding: a reader that aborts on one malformed encoding and silently accepts
another — including a seven-digit value it misreads as a real date — is a
defect worth a human's attention. Under the faithful-only policy it is
reproduced, not corrected, and the finding carries that judgement to the
verdict.
