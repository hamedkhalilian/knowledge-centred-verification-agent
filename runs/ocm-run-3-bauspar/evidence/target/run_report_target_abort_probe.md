# Target run report -- INCOMPLETE (aborted)

Run id: `ocm-run-3-bauspar`  
Input: `staged_inputs/abort_probe.csv`  
Emitted: `2026-09-22T18:07:17Z`

## State

**INCOMPLETE.** The unit's date reader aborted, and under controller directive 01 Rule B an
aborted run emits NO checkpoint file: a partial checkpoint is not comparable (R12). The
`abort_record.json` beside this report is what COMPARE reads instead.

## The abort

| field | value |
|---|---|
| abort_code | `DATE_PARSE_ABORT` |
| row_index | 3 (1-based, in the input table as received, before any sort) |
| column | `Tilgungsbeginn` |
| raw_value | `2013-13-45` |
| rows_completed | 2 |

The trigger, as the directive states it mechanically: the text contains a hyphen, is not
accepted by the standard unambiguous parse, and is the first non-missing element of the vector
the conversion is applied to. `Tilgungsbeginn` is a column the unit parses ITSELF, so the unit
hands the reader one value at a time and that value is always the first element of its own
vector -- which is why every hyphenated unreadable value in such a column aborts, at whatever
row it sits. Had the same value been placed in a harness-coerced column anywhere but the first
non-missing position, it would have gone quietly missing and the run would have completed.

## What was built before the abort

Self-tests ran green before any row was read; their report is `selftest_target*.json`.
The layout reading and the manifest were resolved. No contract record was published, because
the abort stops processing immediately: the unit does not skip the row, does not substitute a
missing value, and does not continue to the next contract (Rule A).

## Notices raised before the abort

- info at harness coercion: column 'erstmalige_zuteilungsanwartschaft' left as raw year-month-day digits -- declared in the input manifest; the unit parses it itself, so every hyphenated unreadable value in it aborts (controller directive 01, path 1)
- info at harness coercion: column 'Tilgungsbeginn' left as raw year-month-day digits -- declared in the input manifest; the unit parses it itself, so every hyphenated unreadable value in it aborts (controller directive 01, path 1)
- info at harness coercion: column 'Vertragsende' left as raw year-month-day digits -- declared in the input manifest; the unit parses it itself, so every hyphenated unreadable value in it aborts (controller directive 01, path 1)
