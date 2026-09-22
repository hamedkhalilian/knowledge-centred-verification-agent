# Target Directives — OCM run 3 (controller → target agent)

Owner-decided facts not in the neutral spec. Binding.

1. **Deliverable:** a TypeScript project at `target_room/`, no framework, no
   bundler. Project name `bauspar-engine`, entry `src/index.ts`. Compiled with
   the TypeScript compiler only.
2. **Declared language level:** written once in `tsconfig.json`
   (`"target": "ES2022"`, `"module": "node16"`, `"strict": true`). The build
   script reads the level from `tsconfig.json` (R13); it is never restated as a
   literal anywhere else.
3. **Dependency budget: zero runtime dependencies** (GR-01). Node's standard
   library only. TypeScript itself is a build-time dependency and is the single
   allow-listed exception. No decimal library: the canonicalisation contract's
   9-significant-digit rendering is implemented in exactly one module,
   `src/canonical.ts`, and a build-time scan must prove no other module formats
   a number for output.
4. **Launch parity (GR-14):** the program demands exactly one input path — the
   contract table — as a de-quoted CLI argument. A second optional argument
   names the valuation date; absent, it is read from the input manifest. No UI
   is required at CORE tier, so no display capability is probed.
5. **Configuration:** the only configuration is the input manifest, read as
   declared data. The harness coercions it declares are applied exactly as
   declared and are never inferred — see directive 01, where that setting
   changes whether the abort path fires.
6. **Artifact browser / figures: NOT REQUIRED.** This is a CORE-tier run.
   GR-04 and GR-05/06 are stood down explicitly rather than by omission. The
   figure geometry in `figures_notes.md` is still specified and still
   checkpointed through the export object, because the positions are computed
   values; nothing needs to be drawn.
7. **Dialogs: not applicable.** No UI.
8. **Memory and progress (GR-09/GR-10/R11):** the staged input is 503 rows, but
   production is 45,881. Stream the input rather than reading it whole, and
   report progress on any stage that can exceed a few seconds. Do not assume
   the row count fits comfortably in memory as parsed objects.
9. **Evidence (GR-16):** write `runs/ocm-run-3-bauspar/evidence/target/` with
   `checkpoints_target.json`, a preconditions report covering the spec's P-01
   to P-13, and a run report. Cache validity, if any caching is added, by
   content hash of the effective configuration, never by timestamp.
10. **Input investigator:** NOT required at CORE tier. The io layer must still
    perform its own content-based checks and diff them against the spec's
    `io_formats` expectations (R7): agree and record it, disagree and halt
    naming both readings. Do not take the spec's expectations as configuration
    — they are claims to verify.
11. **Checkpoints:** emit `checkpoints_target.json` under canonicalisation
    `dec9-half-even-v1`, validating against `checkpoint_schema.json`, for every
    object in the spec's `checkpoint_objects`: `customer_book`,
    `customer_export_rows` and `customers_js_document`. Self-test the
    contract's reference vectors at startup and abort on mismatch.
12. **Encodings (GR-02):** input UTF-8; all emitted artifacts UTF-8 with LF line
    endings. Quoted CLI arguments must survive de-quoting.
13. **Findings policy: FAITHFUL ONLY.** Where the spec records a defect as the
    source's behaviour, implement the defect. Do NOT add corrected behaviour,
    do NOT add switches, and do NOT emit a delta report. GR-12/R9's switch
    mechanism is stood down for this run by owner decision. A divergence is
    then unambiguous: there is no legitimate reason for the two sides to differ.
14. **Detector discipline (R14/R18/GR-13):** every precondition check derives
    its explanation from the data at the point of the finding, keeps FAIL and
    FLAGGED distinct, and is exercised on known-good input before it is allowed
    to FAIL. This run has already lost time twice to checks that passed
    vacuously or cried wolf on sound input; do not add a third.
15. **No silence (R16/GR-08):** every skipped, ignored or fallen-back input is
    named with a reason where it happens, and parse counts reconcile to the
    input total.
16. **Self-tests (GR-13):** run before the checkpoints are emitted, with blind
    spots enumerated (R8).
17. **Abort path:** controller directive 01 is binding. Read it. An aborted run
    emits no checkpoint file and an `abort_record.json` instead.
