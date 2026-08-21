RUN MODE: VERIFY + AUTO-REMEDIATE + REGENERATE + CREATE ARTIFACTS  
AS_OF_DATE: 2026-08-21  
STRICT_BLIND_AUDIT_REQUIRED: false

## Capability declaration (executed before S0)

| Capability | Value | Basis |
|---|---|---|
| input_file_access | YES | Repository files and issue content were read. |
| external_retrieval | NO | No configured authoritative legal retrieval MCP was available for this run. |
| code_execution | YES | Local commands can be executed. |
| file_output | YES | Files can be written in repository workspace. |
| document_compile | NO | No compile target was requested for this markdown/json deliverable set. |
| image_render | NO | No rendered-page inspection capability used. |
| isolated_audit_context | NO | Only same-context second-pass audit is possible. |

## Consequences applied

1. `external_retrieval = NO`: no claim of current-law verification from Gesetze im Internet, BaFin, Bundesbank, EBA, ECB, EUR-Lex, or courts.
2. Time-sensitive legal/accounting propositions are capped as `UNESTABLISHED` unless directly supported by user-supplied authoritative primary text (not supplied here).
3. Accessible licensed professional guidance remains `LICENSE_REQUIRED`.
4. Deliverables are produced as qualified/blocked run artifacts, not a fully verified legal conclusion.
