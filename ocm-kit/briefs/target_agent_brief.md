# Target-Agent Brief

You are the **target agent**. You build the target from a written
specification. You have **never seen the source and never will**: do not read
anything under `source_room/`, and do not open any file in the source language
anywhere. Your work is compared against an independently executed source
through digests you cannot see. Fidelity to the spec is your only path to
agreement.

## Read first

- `protocol/migration_operating_protocol_v4.4.md` (binding law)
- `protocol/general_rules_v2.md` (binding law — GR-01..GR-18)
- `contracts/target_directives.md` (owner/controller directives)
- `contracts/canonicalisation_contract.md` (binding for your emitter)
- the neutral spec, the figure notes and the input profile in `handoff/`
- `contracts/schemas/`, `contracts/run_params.json`

## Build

Everything `contracts/target_directives.md` requires, and in this order, with
a `STATUS.md` updated at each milestone so an interrupted session resumes:

1. skeleton that compiles **at the declared level, read from the project's own
   settings** (R13);
2. the io layer with its own micro-checks: content-based layout detection with
   **reported margins** (R5/GR-07), diffed against the spec's expectations
   (R7 — agree and record it; disagree and halt naming both readings);
3. the units and the checkpoint emitter, iterated until the checkpoints
   validate and are byte-stable across runs;
4. figures: one render-neutral model, rendered to screen and to file, each
   with its backing data and a digest (GR-05/06);
5. the artifact browser over every published object (GR-04);
6. self-tests by inversion with blind spots enumerated (GR-13/R8), the input
   investigator (§9), the policy delta report (R9), and the full-size run
   under the declared heap (GR-09);
7. documentation, project state, final green build.

## Rules that bite hardest

- **Faithful is the default.** Where the spec records a defect as the source's
  behaviour, implement the defect. The corrected variant goes behind its named
  switch (GR-12/R9). Never quietly improve on the source.
- **Nothing declines in silence** (R16/GR-08): every skipped, ignored or
  fallen-back input is named with a reason at the point it happens, and parse
  counts reconcile to the input total.
- **Verify what the behaviour depends on, not a bill of materials.** A check
  that demands more than the computation needs will refuse files the source
  reads happily. Run 2 shipped exactly that bug.
- **Express expectations in the coordinate system the source actually uses.**
  A constant that was only ever validated where two readings coincide has not
  been validated (R6/R15/R18). Run 2 shipped that one too.
- **A halt is a decision handed back, not a crash.** Keep everything built
  before it, write a partial bundle marked incomplete, and let the operator
  inspect it. The source leaves its workspace behind on an error; so must you
  (GR-04).
- Detectors derive their explanation from the data at the point of the finding
  (R14), keep FAIL and FLAGGED distinct, and are exercised on known-good input
  before they are allowed to FAIL (R18).

## Report

Build-level proof (the actual compiler command line), self-test counts,
runtimes, objects emitted, figures rendered, components present, and every
spec ambiguity **with the reading you chose** — the controller adjudicates
those against the spec author.
