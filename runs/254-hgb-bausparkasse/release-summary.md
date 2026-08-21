# Release summary — R-2026-08-21-254-01

## Release state

**BLOCKED**

## Why blocked

- Open blocking source gap: authoritative external legal/supervisory retrieval unavailable (`external_retrieval = NO`).
- Central legal propositions for §254/HGB/Bausparkasse boundary remain `UNESTABLISHED + NOT_RETRIEVED`.
- Licensed professional guidance (IDW RS HFA 35) remains `LICENSE_REQUIRED`.
- Rendered-span entailment gates are `NOT_EVALUATED`; the original run did not create `RenderedSpan` records.
- G-15 is `FAIL`: an artifact manifest now records the produced files and the protocol-minimum split artifacts that were not produced.

## Verification counts

- Claims total: 45
- Supported: 34
- Unestablished: 11
- Primary verified evidence status: 34
- Not retrieved evidence status: 10
- License required evidence status: 1
- Derived claims: 6 (all with derivation rules and premises)

## Deterministic checks

- `kcv-validate runs/254-hgb-bausparkasse/claim-ledger.json`: **PASS** (no findings)
- `pytest`: **PASS**
- `G-02`, `G-04`, `G-06`, `G-07`: **NOT_EVALUATED** (missing rendered-location state)
- `G-15`: **FAIL** (protocol-minimum split artifact set incomplete)

## Produced artifacts

- capability-declaration.md
- source-manifest.json
- claim-ledger.json
- findings.json
- report.md
- release-summary.md
- artifact_manifest.json

## Remaining human/licensed actions

1. Run with authoritative external retrieval for current statutory/supervisory texts.
2. Provide licensed IDW RS HFA 35 text for paragraph-level professional interpretation checks.
3. Resolve D-0001 with the Accounting policy committee and external auditor.
4. Produce the missing split audit/ledger artifacts and re-run the rendered-span and artifact gates.
