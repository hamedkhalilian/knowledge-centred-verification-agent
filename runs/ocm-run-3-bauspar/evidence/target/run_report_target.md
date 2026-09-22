# Target run report -- COMPLETE

Run id: `ocm-run-3-bauspar`  
Input: `staged_inputs/merged_data_synthetic.csv`  
Input manifest: `/home/user/knowledge-centred-verification-agent/staged_inputs/synthetic_manifest.json`  
Valuation date: `2026-03-31` (source: input manifest synthetic_manifest.json field valuation_date)  
Emitted: `2026-09-22T18:07:17Z`

## 1. Self-tests (GR-13, R8, R18)

- passed: **89**, failed: **0**

Good-input control run (R18) -- separation between known-good and known-bad fixtures:

- P-03: good=PASS, bad=FAIL -- abschlussdatum: marker 0, eight-digit valid 0, hyphenated valid 3, unreadable 0 -> 3 reconciles to 3 rows read | einloesungsdatum: marker 0, eight-digit valid 0, hyphenated valid 3, unreadable 0 -> 3 reconciles to 3 rows read | erstmalige_zuteilungsanwartschaft: marker 0, eight-digit valid 2, hyphenated valid 0, unreadable 1 -> 3 reconciles to 3 rows read; first offenders: row 2="2011/04/01" | Tilgungsbeginn: marker 2, eight-digit valid 1, hyphenated valid 0, unreadable 0 -> 3 reconciles to 3 rows read | Vertragsende: marker 2, eight-digit valid 1, hyphenated valid 0, unreadable 0 -> 3 reconciles to 3 rows read || total unreadable 1, of which hyphenated (abort-triggering) 0
- P-05: good=PASS, bad=FAIL -- range 40 .. 40; missing 0; at most 0: 0; greater than 1: 3; distinct raw texts of tariff_amount: 40
- P-06: good=PASS, bad=FLAGGED -- guthaben: missing 0, negative 1, range -11230 .. 12000 | DaBetrag: missing 1, negative 0, range 20000 .. 30000 | bausparsumme_teuro: missing 0, negative 0, range 20000 .. 40000 (in thousands of euro as read; x1000 in the record)
- P-07: good=PASS, bad=FLAGGED -- rows read 3, distinct identifiers 2, identifiers appearing more than once 1; reconciliation rows - distinct = 1; first duplicated: 700001 (never deduplicated: the published record objects keep every row)
- P-10: good=PASS, bad=FLAGGED -- strict-prefix collisions: guthaben_alt begins with guthaben
- P-11: good=PASS, bad=FLAGGED -- text amount values with two or more commas, by field: DaBetrag: 1, bausparsumme_teuro: 0, guthaben: 0, tariff_amount: 0 (each of those becomes missing by behaviour step C2, silently)
- P-13: good=PASS, bad=FLAGGED -- median of loan notional / Bauspar sum over 2 contracts where both are present and the Bauspar sum is positive: 0.001. A median near 1 is expected; near 0.001 or near 1000 would mean the thousands factor was applied on the wrong side or not at all.
- FND-02: good=PASS, bad=FAIL -- non-missing tariff shares: range 40 .. 40, count greater than 1: 3, count at most 0: 0, missing 0, distinct raw texts 40
- FND-04: good=PASS, bad=FLAGGED -- rows 3, distinct identifiers 2, duplicated identifiers 1 (reconciles: 3 rows - 2 distinct = 1 extra rows)
- FND-06: good=PASS, bad=FLAGGED -- values satisfying neither branch: 1 (by field: abschlussdatum 0, einloesungsdatum 0, erstmalige_zuteilungsanwartschaft 1, Tilgungsbeginn 0, Vertragsende 0); of those, hyphenated and therefore ABORT-TRIGGERING: 0
- FND-12: good=PASS, bad=FLAGGED -- check 1 -- all eleven exact names present: yes; check 2 -- other field names having one of the eleven as a strict prefix: guthaben_alt begins with guthaben. The two checks are reported separately, as the finding requires. This target binds by exact name only and never falls back to a prefix; the precondition is what makes the difference unobservable.

Blind spots (R8):

- The canonicalisation and C20 vectors are constants transcribed from the contract and the spec. A transcription error in the spec itself would be invisible to them. Covered structurally by the idempotence and half-place-bracket properties, which share no constant with the vectors.
- The C1 date cases are the behaviours the spec measured on the source. They share the 4/2/2 greedy, non-backtracking scanner assumption with the code under test. Covered by the calendar round-trip, which is independent of the scanner, and by the explicit non-backtracking case 2011/04/01.
- canonicalNumber, the digests and roundRecord all rest on exactOf. A fault there would corrupt all three together and every check above would still agree. Partly covered by the render/re-parse fixed point, which crosses into the runtime's own correctly-rounded decimal conversion.
- The io layer's agreement with the spec is computed with the same quote-aware parser the run uses, so a parser fault would make both readings wrong together. Covered by the naive-split histogram, a structurally different reading of the same bytes.
- Nothing here can detect a systematic MISREADING of the neutral spec: every check is built from the same reading of it. Only the source-side comparison can, and the source's values are withheld until after this emission by design.
- The good/bad fixtures are hand-built, so they calibrate the checks against defects that were thought of. They cannot calibrate against a defect nobody imagined (R15: a threshold calibrated on synthetic data is not calibrated).
- The abort path is exercised by its own probe input, not here: a poisoned row placed in these fixtures would halt the fixture run rather than produce a verdict.

## 2. The io layer's own reading, and the spec's claims (R7)

Detected by content, with margins (R5):

```
delimiter=comma [score 2000 vs semicolon 0, margin 2000]; header on record 1 [score 1000/1000 vs runner-up 515/1000, margin 485/1000]
```

| id | class | claim | spec says | target reads | agree |
|---|---|---|---|---|---|
| IO-ENC | **critical** | the contract table is UTF-8 | UTF-8 | decoded as strict UTF-8 | yes |
| IO-DELIM | **critical** | fields are comma-delimited under proper quoting | comma | delimiter=comma [score 2000 vs semicolon 0, margin 2000]; header on record 1 [score 1000/1000 vs runner-up 515/1000, margin 485/1000] | yes |
| IO-RAGGED | **critical** | every record carries the same number of fields under proper quoting | exactly eleven comma-delimited fields on every line under proper quoting | field-count histogram 11x504 (uniform) | yes |
| IO-NAMES | **critical** | the unit's eleven field names are bound exactly and case-sensitively | BSV, DaBetrag, Tilgungsbeginn, Vertragsende, abschlussdatum, bausparsumme_teuro, contract_type, einloesungsdatum, erstmalige_zuteilungsanwartschaft, guthaben, tariff_amount | all eleven bound: BSV, DaBetrag, Tilgungsbeginn, Vertragsende, abschlussdatum, bausparsumme_teuro, contract_type, einloesungsdatum, erstmalige_zuteilungsanwartschaft, guthaben, tariff_amount | yes |
| IO-BSV | **critical** | the identifier field BSV is present | present; the writer stops with a named refusal when it is not | present | yes |
| IO-SURPLUS | observational | any further field in the table is ignored; the unit selects the eleven it needs by name | surplus fields are reported, never rejected | no surplus fields | yes |
| IO-COERCE | **critical** | the harness coerces exactly abschlussdatum and einloesungsdatum to a date type | abschlussdatum, einloesungsdatum | input manifest declares: abschlussdatum, einloesungsdatum | yes |
| IO-ROWS | observational | 503 data rows and one header row | 503 | 503 | yes |
| IO-QUOTED | observational | 103 of the 503 data lines carry quoted fields containing commas | 103 | 103 | yes |
| IO-TARIFF-SET | observational | distinct tariff share values in full | 0,3000 \| 0,3500 \| 0,4000 \| 0,5000 \| 0.3 \| 0.35 \| 0.4 \| 0.5 \| NA | 0,3000 \| 0,3500 \| 0,4000 \| 0,5000 \| 0.3 \| 0.35 \| 0.4 \| 0.5 \| NA | yes |
| IO-TARIFF-MISSING | observational | 89 of 503 rows carry the missing marker | 89 | 89 | yes |
| IO-TARIFF-RANGE | observational | tariff values run from 0.3 to 0.5 once read | 0.3 .. 0.5 | 0.3 .. 0.5 | yes |
| IO-CTYPE-SET | observational | distinct contract type values in full | (empty) \| BS1 \| BS2 \| BSK \| VL7 | (empty) \| BS1 \| BS2 \| BSK \| VL7 | yes |
| IO-CTYPE-EMPTY | observational | 83 of 503 rows carry the empty contract type | 83 | 83 | yes |
| IO-ID-RANGE | observational | identifiers 800000 to 900023 | 800000 .. 900023 | 800000 .. 900023 | yes |
| IO-DABETRAG | observational | DaBetrag 0 to 295982.79 with 2 missing | 0 .. 295982.79 with 2 missing | 0 .. 295982.79 with 1 missing [reconciliation: 1 empty text + 1 text '0' = 2; behaviour step C2 and the constant amount_missing_markers make the text '0' a ZERO, not a missing value] | **NO** |
| IO-BAUSPAR | observational | bausparsumme_teuro 0 to 50.972 with 3 missing | 0 .. 50.972 with 3 missing | 0 .. 50.972 with 0 missing [reconciliation: 0 empty text + 3 text '0' = 3; behaviour step C2 and the constant amount_missing_markers make the text '0' a ZERO, not a missing value] | **NO** |
| IO-GUTHABEN | observational | guthaben 318.53 to 216706.84 with none missing | 318.53 .. 216706.84 with 0 missing | 318.53 .. 216706.84 with 0 missing | yes |
| IO-DATES | observational | parsed dates from 1998-01-04 to 2043-10-15 | 1998-01-04 .. 2043-10-15 | 1998-01-04 .. 2043-10-15 | yes |
| IO-MARKERS | observational | the missing markers actually present in the date fields are the empty text, 0, 00000000 and NA | (empty) \| 0 \| 00000000 \| NA | (empty) \| 0 \| 00000000 \| NA | yes |
| IO-QUOTE-HAZARD | observational | a reader that splits on the delimiter instead of parsing quoted fields mis-assigns fields silently | 103 lines would show 14 or 15 fields under a naive split | quote-aware histogram 11x504 vs naive-split histogram 11x401, 14x21, 15x82 -- two structurally different readings of the same file (R8) | yes |

**Disagreements.** None of these is computation-critical -- a critical disagreement halts
the run before any row is computed -- so the run continued and both readings are recorded:

- `IO-DABETRAG` DaBetrag 0 to 295982.79 with 2 missing: spec says `0 .. 295982.79 with 2 missing`, target reads `0 .. 295982.79 with 1 missing [reconciliation: 1 empty text + 1 text '0' = 2; behaviour step C2 and the constant amount_missing_markers make the text '0' a ZERO, not a missing value]`.
- `IO-BAUSPAR` bausparsumme_teuro 0 to 50.972 with 3 missing: spec says `0 .. 50.972 with 3 missing`, target reads `0 .. 50.972 with 0 missing [reconciliation: 0 empty text + 3 text '0' = 3; behaviour step C2 and the constant amount_missing_markers make the text '0' a ZERO, not a missing value]`.

## 3. Harness coercions, applied exactly as declared

| column | declared | format inferred from | first non-missing value | row |
|---|---|---|---|---|
| `abschlussdatum` | to_date_class | %Y-%m-%d | `2001-03-01` | 1 |
| `einloesungsdatum` | to_date_class | %Y-%m-%d | `2001-04-01` | 1 |

Columns left as raw year-month-day digits (parsed by the unit itself, so every hyphenated
unreadable value in them aborts): `erstmalige_zuteilungsanwartschaft`, `Tilgungsbeginn`, `Vertragsende`.

## 4. Parse reconciliation (GR-08, R16)

- rows read: **503**
- records published: **503**
- rows refused: **0**

Notices raised, by kind and reason:

- `info|harness coercion|declared in the input manifest; the unit parses it itself, so every hyphenated unreadable value in it aborts (controller directive 01, path 1)` x3
- `info|parse reconciliation (GR-08)|the per-contract calculation is total: it publishes a record for every row it is given` x1

## 5. Checkpoint objects

| object | kind | rows | cols | digest |
|---|---|---|---|---|
| `customer_book` | frame | 503 | 34 | `9ef73ff04d1d8f76e79fe76a0efcc1c7d8d921cbdf133867af8f4a046f0db90b` |
| `customer_export_rows` | frame | 503 | 26 | `afa5ebd0b822d43c441cec219ae5ebd7a70b247e02a3a8f7c2224a8052996f81` |
| `customers_js_document` | frame | 507 | 2 | `fc9c29b403d73516ea3234d83e4e02d55701a4e4ecdbeff906c091ddc20e506a` |

## 6. Preconditions

| id | severity | status | evidence |
|---|---|---|---|
| P-01 | FAIL | **PASS** | all eleven names bound; surplus fields REPORTED not rejected: none |
| P-02 | FAIL | **PASS** | BSV bound at position 1 of the header |
| P-03 | FAIL | **PASS** | abschlussdatum: marker 3, eight-digit valid 0, hyphenated valid 500, unreadable 0 -> 503 reconciles to 503 rows read \| einloesungsdatum: marker 2, eight-digit valid 0, hyphenated valid 501, unreadable 0 -> 503 reconciles to 503 rows read \| erstmalige_zuteilungsanwartschaft: marker 99, eight-digit valid 404, hyphenated valid 0, unreadable 0 -> 503 reconciles to 503 rows read \| Tilgungsbeginn: marker 356, eight-digit valid 147, hyphenated valid 0, unreadable 0 -> 503 reconciles to 503 rows read \| Vertragsende: marker 472, eight-digit valid 31, hyphenated valid 0, unreadable 0 -> 503 recon... |
| P-04 | FLAGGED | **PASS** | abschlussdatum: 1998-01-04 .. 2022-11-20 over 500 parsed, outside 1950-01-01..2100-01-01: 0 \| einloesungsdatum: 1998-05-10 .. 2023-06-29 over 501 parsed, outside 1950-01-01..2100-01-01: 0 \| erstmalige_zuteilungsanwartschaft: 2005-11-11 .. 2035-07-19 over 404 parsed, outside 1950-01-01..2100-01-01: 0 \| Tilgungsbeginn: 2008-03-21 .. 2036-12-26 over 147 parsed, outside 1950-01-01..2100-01-01: 0 \| Vertragsende: 2020-01-20 .. 2043-10-15 over 31 parsed, outside 1950-01-01..2100-01-01: 0 |
| P-05 | FAIL | **PASS** | range 0.3 .. 0.5; missing 89; at most 0: 0; greater than 1: 0; distinct raw texts of tariff_amount: 0,3000 \| 0,3500 \| 0,4000 \| 0,5000 \| 0.3 \| 0.35 \| 0.4 \| 0.5 \| NA |
| P-06 | FLAGGED | **PASS** | guthaben: missing 0, negative 0, range 318.53 .. 216706.84 \| DaBetrag: missing 1, negative 0, range 0 .. 295982.79 \| bausparsumme_teuro: missing 0, negative 0, range 0 .. 50.972 (in thousands of euro as read; x1000 in the record) |
| P-07 | FLAGGED | **PASS** | rows read 503, distinct identifiers 503, identifiers appearing more than once 0; reconciliation rows - distinct = 0 (never deduplicated: the published record objects keep every row) |
| P-08 | FAIL | **PASS** | phase tally done=125, loan=55, oversave=213, save=110 (out of the declared set: 0); goal_source tally fallback_no_tariff=89, tariff=414 (out of set: 0); published positions outside 0..1: 0; saving progress outside 0..1: 0 |
| P-09 | FAIL | **PASS** | rows read 503, records published 503, rows refused 0 (the per-contract calculation publishes a record for every row it is given; its only failure mode is the abort of behaviour step C1, which emits no checkpoint file at all) |
| P-10 | FLAGGED | **PASS** | checked all eleven declared names against all 11 header names: no strict-prefix collision |
| P-11 | FLAGGED | **PASS** | text amount values with two or more commas, by field: DaBetrag: 0, bausparsumme_teuro: 0, guthaben: 0, tariff_amount: 0 (each of those becomes missing by behaviour step C2, silently) |
| P-12 | FAIL | **PASS** | valuation date used: 2026-03-31 (epoch day 20543), source: input manifest synthetic_manifest.json field valuation_date; the unit's own load-time default is 2026-03-31 and its own session override is a value named VAL_DATE -- neither applied here, because this target's launch interface takes the date as an argument or from the input manifest |
| P-13 | FLAGGED | **PASS** | median of loan notional / Bauspar sum over 500 contracts where both are present and the Bauspar sum is positive: 0.975629. A median near 1 is expected; near 0.001 or near 1000 would mean the thousands factor was applied on the wrong side or not at all. |
| FND-01 | FAIL | **PASS** | DaBetrag: 373 values with a dot and no comma, of which 0 have exactly three digits after the last dot (the thousands-dot shape) \| bausparsumme_teuro: 378 values with a dot and no comma, of which 10 have exactly three digits after the last dot (the thousands-dot shape); first: row 24="45.039", row 25="24.387", row 26="10.182", row 28="24.789", row 29="10.621" \| guthaben: 375 values with a dot and no comma, of which 0 have exactly three digits after the last dot (the thousands-dot shape) \| tariff_amount: 332 values with a dot and no comma, of which 0 have exactly three digits after the las... |
| FND-02 | FAIL | **PASS** | non-missing tariff shares: range 0.3 .. 0.5, count greater than 1: 0, count at most 0: 0, missing 89, distinct raw texts 0,3000 \| 0,3500 \| 0,4000 \| 0,5000 \| 0.3 \| 0.35 \| 0.4 \| 0.5 \| NA |
| FND-03 | FLAGGED | **PASS** | published identifiers matching a mantissa followed by e and a signed exponent: 0. The identifier column arrived as TEXT in this run, so the text is used unchanged, with no trimming and no padding. |
| FND-04 | FLAGGED | **PASS** | rows 503, distinct identifiers 503, duplicated identifiers 0 (reconciles: 503 rows - 503 distinct = 0 extra rows) |
| FND-05 | FLAGGED | **PASS** | bands over the UNROUNDED ratio: missing 3, at most 0.5 1, between 0.5 and 2 inclusive 426, greater than 2 73; alarm count from the ROUNDED ratio strictly below 0.5: 1; bridge flag count from the UNROUNDED ratio strictly above 2: 73 -- the two agree on this input |
| FND-06 | FLAGGED | **PASS** | values satisfying neither branch: 0 (by field: abschlussdatum 0, einloesungsdatum 0, erstmalige_zuteilungsanwartschaft 0, Tilgungsbeginn 0, Vertragsende 0); of those, hyphenated and therefore ABORT-TRIGGERING: 0 |
| FND-07 | FAIL | **NOT_EXERCISED** | no standalone page is produced by this build: the target's launch interface (GR-14, target directive 4) takes one input path and an optional valuation date and produces no page. The precondition is therefore not exercised here rather than vacuously passed. It is expected to FAIL for any call with a subset. |
| FND-08 | FLAGGED | **FLAGGED** | allocation estimated 99; contract end absent 472; both 99; phase is done while both were absent: 27 (the last count is this finding's exposure and travels with the verdict) |
| FND-09 | FLAGGED | **PASS** | contracts where published loan portion != published reference - published balance: 104; maximum size of the discrepancy: 1 euro (a discrepancy of more than one euro would mean the rounding rule itself diverges) |
| FND-10 | FLAGGED | **PASS** | published phases: done=125, loan=55, oversave=213, save=110; published phases outside the declared four: 0; contracts with a missing savings ratio (the population the consumers' unreachable branch was written for): 2 |
| FND-11 | FLAGGED | **PASS** | the seven markers of date_missing_markers are implemented in full; the markers actually PRESENT in this input's date fields are: (empty) \| 0 \| 00000000 \| NA. Markers not exercised by this input are named rather than assumed covered. |
| FND-12 | FLAGGED | **PASS** | check 1 -- all eleven exact names present: yes; check 2 -- other field names having one of the eleven as a strict prefix: none. The two checks are reported separately, as the finding requires. This target binds by exact name only and never falls back to a prefix; the precondition is what makes the difference unobservable. |
| FND-13 | FLAGGED | **PASS** | contracts where the published flag and the test 'published ratio at least 0.90' disagree: 0 (that count is the population where the picture and the record contradict each other and it travels with the verdict) |

## 7. Findings policy

FAITHFUL ONLY (target directive 13). Every defect the neutral spec records as the source's
behaviour is implemented as the source does it. There is no switch, no corrected variant and
no delta report, and GR-12/R9's switch mechanism is stood down for this run by owner decision.

## 8. Capabilities NOT exercised

- No artifact browser and no figure rendering: CORE tier, stood down explicitly by target directive 6 (GR-04, GR-05, GR-06).
- No dialog smoke test: there is no user interface, so there is no display capability to probe (GR-03, R17).
- No external retrieval of any kind occurred. No source-side artifact was read.
- The unit's load-time branches (L1-L3), single-contract inspector (C26) and standalone-page writer (C27) are not entry points of this build; their preconditions say NOT_EXERCISED rather than PASS.
- Run at 503 rows. The build has NOT been run on full-size real input (45,881 rows), so GR-09's full-size gate is not discharged.

## 9. Scale note (R11, GR-09)

Both passes stream the file in 64 KiB blocks and keep column-oriented typed arrays, never a
table of parsed row objects. Memory is a fixed cost per cell: 8 bytes for a numeric or date
column, 1 byte for a logical column. The document object holds one string per line, which is
inherent to what it is.

