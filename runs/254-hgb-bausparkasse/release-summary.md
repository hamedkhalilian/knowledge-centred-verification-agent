# Release summary — R-2026-08-21-254-01

## Release state

**BLOCKED**

## Why blocked

- Open blocking source gap: authoritative external legal/supervisory retrieval unavailable (`external_retrieval = NO`).
- Central legal propositions for §254/HGB/Bausparkasse boundary remain `UNESTABLISHED + NOT_RETRIEVED`.
- Licensed professional guidance (IDW RS HFA 35) remains `LICENSE_REQUIRED`.

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

## Produced artifacts

- capability-declaration.md
- source-manifest.json
- claim-ledger.json
- findings.json
- report.md
- release-summary.md

## Remaining human/licensed actions

1. Run with authoritative external retrieval for current statutory/supervisory texts.
2. Provide licensed IDW RS HFA 35 text for paragraph-level professional interpretation checks.
