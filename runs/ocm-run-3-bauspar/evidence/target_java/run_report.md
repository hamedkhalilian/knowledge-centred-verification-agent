# Run report -- ocm-run-3-bauspar, target_java (second independent target)

Unit U01. Tier CORE. Findings policy FAITHFUL ONLY.

## Inputs consumed

- merged_data_synthetic.csv  sha256 7093a21b7197714549c8f8896917eb189b6e3d0a1e3043f3ed26a5f22c1cfa47
- synthetic_manifest.json  sha256 faa2dd1b8f90ed70ddc95dff34a4f8746143f3a89f06b33ba0886f7c33914463

Both are declared in the checkpoint file's `inputs` list, in byte order of their names:
contract table and manifest together, because the manifest's declared harness coercions and
its valuation date are part of what the computation consumed (contract section 7).

## Layout, detected by content

```
delimiter ',' [score 2000 vs ';' 0, margin 2000]; header on row 1 [score 22 vs 12, margin 10]; 11 fields; 503 data records
```

Encoding UTF-8; ragged records 0; records a naive delimiter split would mis-count 103.

## Valuation date

2026-03-31 (input manifest (valuation_date))

## Reconciliation (GR-08)

rows read 503, records published 503, rows refused 0

## Self-tests

94/94 checks green.

- R18 known-GOOD (7 rows): 13/13 PASS, fired: none
- R18 known-BAD values (5 rows): fired P-03=FAIL P-04=FLAGGED P-05=FAIL P-06=FLAGGED P-07=FLAGGED P-10=FLAGGED P-11=FLAGGED
- R18 known-BAD thousands factor (4 rows): fired P-13=FLAGGED

### Blind spots (R8)

- Layers 1-4 are memorised constants: they cannot detect an error that the contract's own vectors and the spec's own vectors share. They are covered structurally by layer 4's disagreement check (the two rounding rules must differ) and by the exact-arithmetic construction, which never consults a table.
- Layer 7's property checks share the engine's reading of the spec: they rule out coding slips, not a misreading of the specification. Only the independent source-side observation can close that, and this agent cannot see it.
- The harness date coercion is modelled from controller directive 01's description of the source language's whole-column conversion. No coerced column in either staged file exercises a FORMAT other than year-month-day with hyphens, so the format-inference branch is covered only for that one format.
- Three of the seven date missing-markers ('00', '0000', '<NA>') do not occur in the staged input, so their handling is exercised only by layer 5, never end to end.
- No identifier in the staged input repeats and none arrives numeric, so FND-03 and FND-04 are unexercised end to end: their preconditions pass vacuously and are reported as such, not as evidence.
- Every threshold here was seen only on synthetic data (R15). None of them may produce a FAIL on real input before it has seen real input; the run report says so in the verdict, and the verdict is capped at PROVISIONAL by R2 regardless.

## Preconditions

| id | severity | status | explanation |
|---|---|---|---|
| P-01 | FAIL | PASS | all eleven declared names present; 0 surplus field(s) ignored by name selection |
| P-02 | FAIL | PASS | BSV is present, so the browser-data writer's second named refusal cannot fire |
| P-03 | FAIL | PASS | all 2515 date cells classify as marker, eight-digit valid or hyphenated valid; none unreadable |
| P-04 | FLAGGED | PASS | every parsed date range lies inside 1950-01-01..2100-01-01; no field shows the year-below-100 signature of a two-digit year |
| P-05 | FAIL | PASS | every non-missing share is a fraction of one, so the unit's direct multiplication by an amount in euro is right (FND-02 not exposed here) |
| P-06 | FLAGGED | PASS | no negative amount in any of the three fields |
| P-07 | FLAGGED | PASS | every identifier occurs once, so FND-04's browser-keeps-the-last against harness-keeps-the-first cannot bite in this run |
| P-08 | FAIL | PASS | every published phase, goal source, position and saving progress is inside its declared shape |
| P-09 | FAIL | PASS | the three counts reconcile and nothing was refused |
| P-10 | FLAGGED | PASS | no field name begins with a declared name, so the source's prefix fallback (FND-12) cannot bind the wrong field |
| P-11 | FLAGGED | PASS | no text amount carries a second comma, so the silent-missing clause of C2 is not reached here |
| P-12 | FAIL | PASS | the valuation date is inside 1950-01-01..2100-01-01 |
| P-13 | FLAGGED | PASS | the median ratio is 0.9755, near the 1 the unit's own documentation expects for an ordinary contract, so the factor is the right way up |

## Findings exposure (faithful-only; nothing repaired)

- **FND-01** DaBetrag: no text value has a dot, no comma and more than two digits after the last dot; this field cannot be read a thousand times too small here
- **FND-01** bausparsumme_teuro: 345 value(s) with a dot, no comma and more than two digits after the last dot -- their range 10.008..50.972 OVERLAPS the range of the field's unambiguously-spelled values 0..50.875 (125 of them), so the third decimal is this field's own precision and not a thousands dot; the finding is NOT exposed here
- **FND-01** guthaben: no text value has a dot, no comma and more than two digits after the last dot; this field cannot be read a thousand times too small here
- **FND-01** tariff_amount: no text value has a dot, no comma and more than two digits after the last dot; this field cannot be read a thousand times too small here
- **FND-02** tariff shares greater than 1 (percent points would be out by a hundred): 0; min 0.3, max 0.5
- **FND-03** published identifiers in exponent form: 0 (the column arrives as text, so the default numeric conversion never runs)
- **FND-04** rows 503, distinct identifiers 503, duplicated identifiers 0 (the browser keeps the LAST entry per key; the quality harness keeps the FIRST row)
- **FND-05** published ratio missing 3, at most 0.5 1 (strictly below 0.5: 1), 0.5..2 inclusive 426, above 2 73; red alarms raised 1. The alarm is STRICTLY LESS THAN 0.5 on the already-rounded ratio, so it must equal the strictly-below band: it does. The bridge flag, by contrast, was decided on the UNROUNDED ratio strictly above 2.
- **FND-08** allocation estimated 99, contract end absent 472, both 99, phase 'done' while both were absent 27 (the last count is this finding's exposure)
- **FND-09** published loan portion differs from published reference minus published balance in 104 contract(s); largest difference 1 euro (more than one euro would mean the rounding rule itself diverges)
- **FND-10** contracts with a missing savings ratio: 2 -- the population the consumers' unreachable 'nodata' phase was written for; the unit publishes only the four declared phases
- **FND-11** of the seven markers the code recognises, 3 are never exercised by this input: '00' '0000' '<NA>'
- **FND-12** field names that shadow a declared name by prefix: none
- **FND-13** contracts where the published flag and the test 'published ratio at least 0.90' disagree: 0 (the picture and the record contradict each other there)
- **FND-06** the abort path is exercised by the separate probe input, not by this table; unreadable hyphenated date values in this table: 0 (any such value would have aborted the run)
- **FND-07** not exercised at CORE tier: the standalone-page writer is not built (no UI, no template), so the count it misreports cannot be observed here

## Checkpoint objects

| object | rows | cols | digest |
|---|---|---|---|
| customer_book | 503 | 34 | `9ef73ff04d1d8f76e79fe76a0efcc1c7d8d921cbdf133867af8f4a046f0db90b` |
| customer_export_rows | 503 | 26 | `afa5ebd0b822d43c441cec219ae5ebd7a70b247e02a3a8f7c2224a8052996f81` |
| customers_js_document | 507 | 2 | `fc9c29b403d73516ea3234d83e4e02d55701a4e4ecdbeff906c091ddc20e506a` |

## Spec expectations diffed (R7)

| expectation | spec | ours | verdict |
|---|---|---|---|
| the eleven declared field names are present, spelled exactly | all eleven present | all eleven present | AGREE |
| surplus fields are ignored by name selection, never rejected | any further field is ignored, never a halt | this reader selects the eleven by name; 0 surplus field(s) present, all ignored, none rejected | AGREE |
| the identifier field BSV is present | present | present | AGREE |
| data rows | 503 | 503 | AGREE |
| fields per line under proper quoting | 11 | 11 | AGREE |
| encoding | UTF-8 | UTF-8 | AGREE |
| lines whose amounts contain commas inside quotes (a naive splitter mis-counts these) | 103 | 103 | AGREE |
| header names | BSV,DaBetrag,Tilgungsbeginn,Vertragsende,abschlussdatum,bausparsumme_teuro,contract_type,einloesungsdatum,erstmalige_zuteilungsanwartschaft,guthaben,tariff_amount | BSV,DaBetrag,Tilgungsbeginn,Vertragsende,abschlussdatum,bausparsumme_teuro,contract_type,einloesungsdatum,erstmalige_zuteilungsanwartschaft,guthaben,tariff_amount | AGREE |
| tariff share distinct RAW spellings, in full | 0,3000/0,3500/0,4000/0,5000/0.3/0.35/0.4/0.5/NA | 0,3000/0,3500/0,4000/0,5000/0.3/0.35/0.4/0.5/NA | AGREE |
| tariff share rows carrying the missing marker | 89 | 89 | AGREE |
| tariff share range once read | 0.3 .. 0.5 | 0.3 .. 0.5 | AGREE |
| contract type distinct values, in full | ,BS1,BS2,BSK,VL7 | ,BS1,BS2,BSK,VL7 | AGREE |
| rows carrying the empty contract type | 83 | 83 | AGREE |
| identifier range | 800000 .. 900023 | 800000 .. 900023 | AGREE |
| DaBetrag range | 0 .. 295982.79 | 0 .. 295982.79 | AGREE |
| DaBetrag values that are MISSING once read | 2 | 1 | DIFFER |
|   ... reconciliation attempt for the count above | 2 (spec) | missing 1 + zero-valued 1 = 2 | AGREE |
| bausparsumme_teuro range | 0 .. 50.972 | 0 .. 50.972 | AGREE |
| bausparsumme_teuro values that are MISSING once read | 3 | 0 | DIFFER |
|   ... reconciliation attempt for the count above | 3 (spec) | missing 0 + zero-valued 3 = 3 | AGREE |
| guthaben range | 318.53 .. 216706.84 | 318.53 .. 216706.84 | AGREE |
| guthaben values that are MISSING once read | 0 | 0 | AGREE |
|   ... reconciliation attempt for the count above | 0 (spec) | missing 0 + zero-valued 0 = 0 | AGREE |
| parsed date range across the five date fields | 1998-01-04 .. 2043-10-15 | 1998-01-04 .. 2043-10-15 | AGREE |
| date missing-markers actually present in the stand-in | ,0,00000000,NA | ,0,00000000,NA | AGREE |
| harness coercion to a date type, as DECLARED in the manifest | abschlussdatum,einloesungsdatum | abschlussdatum,einloesungsdatum | AGREE |
| harness leaves these as raw digits, as DECLARED in the manifest | erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende | erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende | AGREE |
| identifiers are unique per row | unique | unique | AGREE |

## Not verified

- The real contract table is absent; every fact about the input came from a generated
  stand-in. Under R2 the verdict is capped at PROVISIONAL however well the two sides agree.
- No source-side value was seen by this agent, by construction (R21).
- FND-07 is unobservable at CORE tier: no standalone page writer is built.
- Every threshold here has only ever seen synthetic data (R15).

Computed 503 contracts in 0.08 s.
