# Target Directives (controller → target agent)

Owner-decided facts the target agent needs that are not in the neutral spec.

1. **Deliverable:** an Eclipse-importable Java project (plain JDT — `.project`,
   `.classpath`, `.settings/org.eclipse.jdt.core.prefs`). Project name:
   `ocm-hedging`. Root package: `ocm`. No Maven/Gradle (GR-01).
2. **Declared language level: Java 17.** Written once in
   `.settings/org.eclipse.jdt.core.prefs` (`compliance=17`); the build script
   reads it from there (R13) and compiles with `javac --release "$LEVEL"
   -Xlint:all`. Provide `build.sh` (POSIX) and `build.bat` (Windows) both reading
   the same setting. `SelfTest` runs at that level.
3. **Zero external dependencies** (GR-01): JDK only. Swing for UI; StAX
   (`javax.xml.stream`) + `java.util.zip` for XLSX; hand-written SVG for figures;
   hand-rolled minimal JSON writer/reader. `BigDecimal` only inside the
   allow-listed canonical serialiser (GR-11): exactly one class, named
   `CanonicalNumber`, and a build-time scan proves it appears nowhere else.
4. **Launch parity (GR-14):** the program demands three input paths (portfolio
   text export, loans workbook, market workbook) — as de-quoted CLI arguments
   (GR-02), as remembered picker choices, or from the config file. Nothing else
   is required at launch. `--headless` runs the pipeline + evidence without UI;
   display capability is probed by exercising it (R17), never by a flag.
5. **Config file:** raw line parser, never `Properties.load` (GR-02); saving
   rewrites only owned values and preserves every comment and blank line
   (GR-15/R19), verified by a line/comment/setting count round-trip test.
6. **Artifact browser (GR-04):** permanent component; every published object of
   every unit openable as a live, sortable, filterable table; filtered view
   exportable to CSV. **Figures section (GR-05):** every figure rendered by a
   Java2D panel and written as SVG into `evidence/<run>/figures/`, both from the
   same render-neutral model; each figure writes a companion CSV + digest
   (GR-06).
7. **Dialogs (GR-03):** always-on-top owner, console line announcing every
   dialog, `dispose()` on close; JVM must exit after close. Prompting can be
   disabled entirely for scheduled runs.
8. **Memory (GR-09/R11):** stream the portfolio text export into primitive
   arrays; no boxed bulk collections; budget = full pipeline in a 2 GB heap;
   progress output on every stage that can exceed a few seconds (GR-10).
9. **Evidence (GR-16):** every run writes `evidence/<run-id>/` with checkpoints,
   preconditions report, runtime trace, figures (SVG+CSV+digest), run report;
   cache validity by content hash of the entire effective configuration, never
   by timestamp. `project_state.json` at repo root updated per delivery (GR-18).
10. **Input investigator (§9):** a standalone mode (`--investigate`) profiling
    the three inputs without any convenience reader: true grid coordinates,
    field-count distribution, text-cells per column, date-like vs rate-like
    counts per row with magnitude separation chosen from data, key vectors in
    full, layout anchors **with margins** (R5), date-range plausibility (P18).
    Emits `input_profile.json` against the schema.
11. **Checkpoints:** emit `checkpoints_target.json` per the canonicalisation
    contract `dec9-half-even-v1` and `checkpoint_schema.json`, for every object
    the spec's `checkpoint_objects` lists.
12. **Encodings (GR-02):** portfolio text default ISO-8859-1; all emitted
    artifacts UTF-8. Windows paths (`C:\...`) and quoted arguments must survive.
13. **Findings (GR-12/R9):** faithful behavior is the default; each catalogued
    finding's corrected behavior is a named policy in the config, one setting
    away; `--delta-report` runs both ways and reports the numeric delta per
    finding.
14. **Detectors (R14/R18/GR-13):** every detector derives its explanation from
    the data at the point of finding; FAIL vs FLAGGED kept distinct; diagnostic
    statistics robust (`median(abs(steps))` not `abs(median(steps))`); each
    detector exercised on known-good input before it may FAIL.
15. **No silence (R16/GR-08):** every skipped/ignored/fallen-back input named
    with a reason at the point it happens; parse reconciliation counts printed
    (read / excluded / failed reconciling to total); truncated displays say so.
16. **Self-tests (GR-13):** inversion-based, run before packaging, at the
    declared level; blind spots enumerated in the output (R8).
