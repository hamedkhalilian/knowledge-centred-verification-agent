# Target Directives — TEMPLATE (controller → target agent)

Owner-decided facts the target agent needs that are **not** in the neutral
spec: the deliverable's shape, language and toolchain, what the program must
demand at launch, and which cross-cutting protocol obligations apply.

**This file ships as a template on purpose.** It previously carried run 2's
directives verbatim — an Eclipse-importable Java/Swing project named
`ocm-hedging`, Java 17, three spreadsheet inputs, StAX for XLSX. A target agent
handed those for any other migration builds the wrong program in the wrong
language, and does so confidently, because directives read as owner authority
rather than as a guess. That is the same leak class as `alias_map.json` and
`run_params.json` (lessons, finding 9), in the one file whose whole purpose is
to be obeyed.

Each run writes its own copy into its run directory and points the target agent
at that. The kit keeps only the checklist below.

## What every run's directives must decide

1. **Deliverable** — project shape, name, root module/package, and whether any
   build system is permitted (GR-01).
2. **Declared language level / runtime version** — written once in the
   project's own settings, and read from there by the build script (R13), never
   duplicated as a literal in two places.
3. **Dependency budget** — GR-01 defaults to zero external dependencies.
   Name any allow-listed exception and confine it to exactly one named module,
   with a build-time scan proving it appears nowhere else (the run-2 precedent
   is a decimal type allowed only inside the canonical serialiser, GR-11).
4. **Launch parity (GR-14)** — exactly what the program demands at launch and
   by which routes; de-quoting and path handling (GR-02); how a headless run is
   requested, and that display capability is probed by exercising it (R17),
   never by a flag.
5. **Configuration handling** — raw line parsing, and whether saving must
   preserve comments and blank lines (GR-15/R19).
6. **Artifact browser (GR-04)** and **figures (GR-05/06)** — required at FULL
   tier; state explicitly if a CORE-tier run omits them, rather than leaving
   the omission to be inferred.
7. **Dialog and exit behaviour (GR-03)**, if there is a UI.
8. **Memory and progress budget (GR-09/GR-10/R11)** — the heap the full-size
   run must fit, and which stages report progress.
9. **Evidence layout (GR-16)** — what each run writes, and that cache validity
   is by content hash of the effective configuration, never by timestamp.
10. **Input investigator (§9)** — whether the target ships its own profiler,
    and against which schema it emits.
11. **Checkpoints** — the canonicalisation contract id, the schema, and that
    every object in the spec's `checkpoint_objects` is emitted.
12. **Encodings (GR-02)** — input default and emitted-artifact encoding.
13. **Findings policy (GR-12/R9)** — faithful-only, or faithful plus corrected
    behaviour behind named switches. If switches are permitted, say how the
    delta between the two is reported.
14. **Detector discipline (R14/R18/GR-13)** — explanations derived from the
    data at the point of finding, FAIL and FLAGGED kept distinct, robust
    diagnostic statistics, and every detector exercised on known-good input
    before it is allowed to FAIL.
15. **No silence (R16/GR-08)** — every skipped, ignored or fallen-back input
    named with a reason where it happens, and parse counts reconciling to the
    input total.
16. **Self-tests (GR-13)** — inversion-based, run before packaging, at the
    declared level, with blind spots enumerated (R8).
