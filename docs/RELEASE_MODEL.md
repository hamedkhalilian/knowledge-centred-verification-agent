# Release model

## States

Each gate has one of four states:

| State | Meaning |
|---|---|
| `PASS` | evaluated and satisfied |
| `FAIL` | evaluated and not satisfied |
| `NOT_EVALUATED` | required but not performed; blocks full release |
| `NOT_APPLICABLE` | genuinely irrelevant to this run |

The overall run may be:

- `RELEASED` — all applicable required gates pass;
- `QUALIFIED_RELEASE` — the protocol permits a disclosed limitation that does
  not invalidate the delivered artifact;
- `BLOCKED` — a required gate fails or remains unevaluated, or a genuine human
  or licensed-source decision remains.

Blocked release does not cancel artifact production. When file output is
available, corrected working documents, the ledger, findings, and audit artifacts
must still be produced and clearly marked.

## Minimum release sequence

1. Validate object structure and graph invariants.
2. Verify source-dependent claims to the available evidence level.
3. Record unresolved decisions and unavailable licensed sources.
4. Apply ledger-level remediation.
5. Propagate changes through dependent claims.
6. Regenerate every affected rendered span.
7. Re-run deterministic and semantic checks.
8. Compile and visually inspect when the deliverable requires it.
9. Record gate states and the final release status.

## Versioning

Protocol versions use semantic intent:

- patch: clarification without changing accepted outputs;
- minor: new compatible rule, object, or gate;
- major: incompatible ledger or lifecycle semantics.

Run records pin the exact prompt version. Git tags should identify repository
releases once protocol, schemas, validator, tests, and documentation agree.

