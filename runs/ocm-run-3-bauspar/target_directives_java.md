# Target Directives — OCM run 3, SECOND TARGET (Java)

Owner-decided facts not in the neutral spec. Binding on the Java target agent.

This is a **second, independent IMPLEMENT against the same neutral spec**. It is
not a port of the first target and must not become one. DISCOVER, PROFILE,
SPECIFY and OBSERVE_SOURCE are already complete and unchanged; only IMPLEMENT
and OBSERVE_TARGET re-run.

## Why this run exists

The first target's agent named its own sharpest limit: it wrote a second
implementation to cross-check itself, but both shared *its* reading of the
spec, so the cross-check ruled out coding slips and nothing more. A second
target, written by a different agent in a different language from the same
spec, tests the **specification** rather than the code.

If this target lands on the same three digests, three independent
implementations in three languages agree, and the spec is shown to determine
the behaviour rather than merely to be satisfiable. If it diverges, the
divergence locates a place where the spec under-determines what the source
does — which is a finding worth more than another agreement.

## The barrier, extended

The usual prohibition holds: the target never sees the source. **This run adds
one more**, and it is what the whole exercise rests on:

> The Java target agent must not see the TypeScript target either.

A second implementation that has read the first is a translation, and its
agreement proves only that translation works. `target_room/` is therefore
quarantined alongside `source_room/`, every file in the source language, and
the evidence directory holding both sides' digests.

## Directives

1. **Deliverable:** a plain JDK project at `target_room_java/`, no build system,
   no framework. Project name `bauspar-engine-java`, root package `bauspar`,
   entry `bauspar.Main`.
2. **Declared language level: Java 21.** Written once in
   `target_room_java/project.properties` as `java.level=21`. `build.sh` reads
   the level from there (R13) and compiles with `javac --release "$LEVEL"
   -Xlint:all`. The level is never restated as a literal anywhere else.
3. **Dependency budget: zero.** JDK standard library only (GR-01). No Maven, no
   Gradle, no downloaded jars. `BigDecimal` is allow-listed **only** inside the
   canonical serialiser — exactly one class, `bauspar.CanonicalNumber` — and a
   build-time scan must prove it appears in no other source file. It may not
   appear in any computation path: the unit's arithmetic is double arithmetic
   and must stay so, or the digests will differ in ways that have nothing to do
   with the specified behaviour.
4. **Launch parity (GR-14):** exactly one required argument, the contract table
   path, de-quoted (GR-02). An optional second argument names the valuation
   date; absent, it is read from the input manifest. No UI at CORE tier, so no
   display capability is probed.
5. **Configuration:** the input manifest only. Its declared harness coercions
   are applied exactly as declared and never inferred — that setting decides
   whether the abort path fires (controller directive 01).
6. **Artifact browser / figures: NOT REQUIRED.** CORE tier. GR-04 and
   GR-05/GR-06 are stood down explicitly, not by omission.
7. **Dialogs: not applicable.** No UI. Do not build Swing. The previous
   migration's Swing requirement belongs to a different run and a different
   source.
8. **Memory and progress (GR-09/GR-10/R11):** the staged input is 503 rows;
   production is 45,881. Stream the input rather than reading it whole. Do not
   build a boxed collection of parsed row objects.
9. **Evidence (GR-16):** write `runs/ocm-run-3-bauspar/evidence/target_java/`
   with `checkpoints_target.json`, a preconditions report covering P-01..P-13,
   and a run report.
10. **Input investigator:** not required at CORE tier. The io layer must still
    make its own content-based checks and diff them against the spec's
    `io_formats` expectations (R7): agree and record it, disagree and halt
    naming both readings. The spec's expectations are claims to verify, never
    configuration to adopt.
11. **Checkpoints:** emit `checkpoints_target.json` under canonicalisation
    `dec9-half-even-v1`, validating against `checkpoint_schema.json`, for every
    object in the spec's `checkpoint_objects`: `customer_book`,
    `customer_export_rows`, `customers_js_document`. Self-test the contract's
    reference vectors at startup and abort on mismatch.

    **The inputs list must declare BOTH files consumed** — the contract table
    and the manifest — because contract §7 makes two checkpoint files
    comparable only if their input lists agree, and the source declares both.
    Entries are emitted in byte order of their names. The first target's run
    lost a cycle to exactly this; you are being told so you do not repeat it.
12. **Encodings (GR-02):** input UTF-8; all emitted artifacts UTF-8 with LF line
    endings. Quoted arguments must survive de-quoting.
13. **Findings policy: FAITHFUL ONLY.** Where the spec records a defect as the
    source's behaviour, implement the defect. No corrected variants, no
    switches, no delta report. GR-12/R9's switch mechanism is stood down by
    owner decision. A divergence is then unambiguous.
14. **Detector discipline (R14/R18/GR-13):** every precondition check derives
    its explanation from the data at the point of the finding, keeps FAIL and
    FLAGGED distinct, and is exercised on known-good input before it may FAIL.
15. **No silence (R16/GR-08):** every skipped, ignored or fallen-back input
    named with a reason where it happens; parse counts reconcile to the total.
16. **Self-tests (GR-13):** run before the checkpoints are emitted, at the
    declared level, with blind spots enumerated (R8).
17. **Abort path:** controller directive 01 is binding. Read it. An aborted run
    emits no checkpoint file and an `abort_record.json` instead.

## Two traps this language will set for you

Recorded because the controller has already measured them on the other side,
and neither is guesswork:

- **The rounding rule is not your language's rounding.** The spec states the
  rule and publishes sixteen measured reference vectors. It is not
  multiply-round-divide, and it is not `Math.round`. `10 × 365.25 = 3652.5`
  must land on **3652**. Re-check all sixteen at startup.
- **A second rounding rule governs the browser document**, and it is a
  different rule. Using one for both will diverge.
