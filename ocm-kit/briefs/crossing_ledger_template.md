# Crossing Ledger

Every artifact that crosses a room boundary, in order. Sanitisation = barrier
scan + schema validation where applicable.

| # | When (UTC) | Artifact | From → To | Sanitisation | Note |
|---|---|---|---|---|---|
| 1 | 2026-08-28 | protocol/*.md (owner's law) | owner → both rooms | none needed (owner documents) | v4.4 + GR rev 2 |
| 2 | 2026-08-28 | contracts/canonicalisation_contract.md, schemas/*, controller_flow.md | controller → both rooms | authored controller-side, source-neutral | reconstructions; absence of originals recorded as finding |
| 3 | 2026-08-28 | contracts/target_directives.md | controller → target room | authored controller-side | owner decisions + GR restatement |
| 4 | 2026-08-28 | source files (11 .R) | owner → source room only | — | target room forbidden; enforced by prompt + post-hoc syntax scan of target tree |
| 5 | 2026-08-28 | inputs/ (3 synthetic files + full-size variant) | controller → both rooms (read-only) | provenance recorded synthetic in input_profile | shared givens |
| 6 | 2026-08-28 | neutral_spec.json, source_figures_notes.md | source room → target room | controller barrier scan (detector leak-validated, 6 patterns; 0 hits) + jsonschema PASS + controller line-by-line review of unit semantics against the source | flow_manifest_source withheld (controller-side; target forms its own structural opinion) |
| 7 | 2026-08-28 | evidence/input_profile.json | controller → target room | authored controller-side (raw profiler) | PROFILE-state artifact |
| — | — | checkpoints_source.json | **withheld from target room** | — | R21: first target emission must be independent; comparison is controller-side |
| 8 | 2026-08-29 | comparison result (divergence location only: object name, "digests differ") | controller → source room | value-free defect routing | routed as spec defect per controller_flow |
| 9 | 2026-08-29 | neutral_spec.json v1.1.0 (name lists pinned, hint corrected, stale prose fixed) | source room → target room | barrier scan (0 hits) + jsonschema + controller diff v1.0.0→v1.1.0 (one notes string + U01 constants + U07 prose) | second and final spec crossing |
| 10 | 2026-08-29 | final comparison verdict (393/393) + doc-hygiene request + 2 graph-edge questions | controller → target room | value-free | target reworded 4 comments, removed/gated 2 manifest edges; digests unchanged |

**Independence note:** at no point did source checkpoint VALUES cross to the
target room. The two divergence-era messages carried only the object name and
the fact of digest inequality; the fix travelled as a spec amendment.
