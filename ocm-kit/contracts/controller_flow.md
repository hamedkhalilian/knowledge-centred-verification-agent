# Controller Flow — reconstruction

**Status:** `controller.md` (referenced by general_rules_v2.md as defining the
state machine) was **not present in ocm_v4.4.zip**. This file reconstructs the
minimum flow implied by the protocol's own references (states named in §2's
artifact table, gates named in GR enforcement). Recorded as a bundle finding;
supersede with the original when it surfaces.

## Roles and contexts (R21 — owner decision: structural, this run)

| Role | Context | Sees source? | Sees target? |
|---|---|---|---|
| Controller | this session | yes | yes |
| Source agent | separate agent context A | yes | **no** |
| Target agent | separate agent context B | **no** | yes (its own work) |

Only files cross. Everything that crosses is logged in the crossing ledger,
barrier-scanned where it flows source → target, and schema-validated.

## States

```
DISCOVER        controller stages inputs; source room / target room isolated
PROFILE         input_profile.json emitted by a non-source-language profiler (§9, R2, R3)
SPECIFY         source agent emits neutral_spec.json (+ flow_manifest source side,
                findings, io expectations per R7); controller barrier-scans (leak-
                validated detector), schema-validates, then releases to target room
OBSERVE_SOURCE  source pipeline EXECUTED (R20a); checkpoints_source.json emitted
                under dec9-half-even-v1; harness patches recorded in the artifact
IMPLEMENT       target agent builds the target from the spec; S4 exit gate below
OBSERVE_TARGET  target run emits checkpoints_target.json + runtime_trace.json
COMPARE         controller diffs digests (layer 5); divergence -> diagnose ->
                route to the responsible side; S6 gate below
VERIFY          remaining ladder layers; R10 graph diff with dispositions
VERDICT         verdict.json; caps computed per R2/R15/R20/R21; GR-17 checklist
```

## Gates (from general_rules_v2.md)

- **S4 exit** (before a build is packaged): GR-01, 03, 04, 05, 07, 08, 09, 10, 11, 13, 14, 15, 17
- **S6 COMPARE** (as contract categories): GR-06, 08, 12, 16
- A violated GR is a named finding (`GR-xx VIOLATION`), never a silent regression.

## Crossing rules (R7, R21)

source → target may carry: the neutral spec, the contracts and schemas, io-format
**expectations to verify**, finding statements. It may **not** carry: source
syntax (mechanically scanned), source-side runtime detections as settings, or
source checkpoint **values** prior to the first independent target emission.
After both sides have emitted independently, the controller may share divergence
locations and value pairs for diagnosis; the independence of the **first**
agreement is what the verdict cites.

target → source may carry: nothing except controller-mediated questions about
spec ambiguity, phrased without target code.

## Divergence routing

1. Reproduce the mismatch from the two checkpoint files alone.
2. Classify: spec defect (spec under-determines or mis-states the source) →
   source agent amends spec, version bumped; target defect → target agent fixes
   against the spec; contract defect (canonicalisation ambiguity) → controller
   amends contract, both emitters re-run.
3. Every routed divergence and its resolution is appended to the comparison
   report; none is resolved by copying values across.

## Controller tool invocations

Every tool below is declared per run. Nothing in `contracts/` ships a previous
run's names, so each of these files must be filled during DISCOVER/SPECIFY
before the state that consumes it.

| Declared per run | Filled during | Consumed by |
|---|---|---|
| `contracts/source_probes.csv` | DISCOVER | `tools/r_source_detector.R` (PROFILE) |
| `contracts/detector_spec_bindings.json` | SPECIFY | `tools/check_detector_vs_spec.py` (R3 gate) |
| `contracts/alias_map.json` | SPECIFY | `tools/render_graphs.py` (VERIFY, FULL tier) |
| `contracts/run_params.json` | DISCOVER | both agents (OBSERVE_*) |

### PROFILE — inputs

The kit ships **no** profiler. PROFILE's profiler is written per run, in a
non-source language, against the real staged inputs;
`tools/examples/profile_inputs_run2_hedging.py` is a worked shape whose raw
readers (zipfile + XML for xlsx, byte-level for text exports) are reusable.
The same holds for synthetic generation —
`tools/examples/gen_synthetic_run2_hedging.py`. Anything a stand-in shows is
tagged `observed_in_synthetic_input`, never `observed_in_real_input`, and caps
the verdict under R2.

### PROFILE — source detector

```sh
Rscript tools/r_source_detector.R \
  --r-dir source_room \
  --probes contracts/source_probes.csv \
  --out-dir evidence/source_detector
```

Run this **before** the spec is written (lessons, finding 2). With no probes
declared the detector records `RSD-NO-PROBES` rather than falling silent: an
empty findings file must never be read as "the source has no anchors".

### SPECIFY exit — the R3 gate

```sh
python3 tools/check_detector_vs_spec.py \
  --detector evidence/source_detector/r_source_field_groups.csv \
  --spec source_room/out/neutral_spec.json \
  --bindings contracts/detector_spec_bindings.json
```

Exit codes are **three-valued on purpose**:

| Exit | Meaning | Controller action |
|---|---|---|
| 0 | every declared pair was compared and agrees | proceed to release the spec |
| 1 | a declared name vector diverges | spec defect; route per divergence routing |
| 2 | the gate could not compare meaningfully | **halt**; the gate did not run |

Exit 2 covers an empty or unparsable detector file, a detector silent about the
bound source file, a pair empty on both sides, and any spec name vector or
detector group that no binding covers. These are not agreements. A gate that
reports green having compared nothing is the failure mode this gate exists to
prevent, so "no comparison" is never allowed to share an exit code with
"compared and agreed".

Waiving a comparison is legitimate but must be explicit —
`waived_spec_constants` / `waived_detector_groups` in the bindings file, with
the reason recorded in the crossing ledger. Silence is not a waiver.

### VERIFY (FULL tier) — graph render

```sh
python3 tools/render_graphs.py \
  source_room/out/flow_manifest_source.json \
  evidence/flow_manifest_target.json \
  contracts/alias_map.json \
  evidence
```

Unit order in the rendered diagram is the order of `entries` in the alias map,
and the run id in the figure footer is the map's `run_id`. Modules the map does
not declare sort last, by id, so an undeclared module is visibly out of place
rather than quietly interleaved.
