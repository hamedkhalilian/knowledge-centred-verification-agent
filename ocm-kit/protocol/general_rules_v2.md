# OCM v4.4 — General Rules (GR), revision 2

**Status:** protocol-level, binding. Applies to every migration unit, every build, every conversation.
**Relation to other documents:** `controller.md` defines *how* a unit moves through the state machine.
`migration_operating_protocol_v4.4.md` defines the binding rules of method. This file defines invariants
that hold *regardless of which unit* is being migrated. Preconditions (Pxx) are per-unit facts about the
source; General Rules (GRxx) are cross-unit facts about the target and the process.
**Origin:** every rule below was learned empirically during migration #1 (hedging pipeline, R → Java,
865k-contract portfolio). None is theoretical.

**Enforcement:** the Controller checks the GR checklist at two gates:
- **S4 exit** (before a build is packaged): GR-01, 03, 04, 05, 07, 08, 09, 10, 11, 13, 14, 15, 17
- **S6 COMPARE** (as contract categories): GR-06, 08, 12, 16

A violated GR is a named finding (`GR-xx VIOLATION`), never a silent regression.

**Revision 2 changes:** GR-03, GR-09, GR-11 and GR-15 had no enforcement point in revision 1 —
they appeared in neither gate nor the delivery checklist. GR-03 and GR-09 are the rules born from
the two most expensive failures in the record (a modal dialog behind the IDE, and an
out-of-memory presenting as a freeze), and they were exactly the two nobody was obliged to check.
All four now have executable gates in GR-17. GR-04 is linked to R10. GR-11 gains a clause
separating computation from serialisation.

---

## A. Target platform

**GR-01 — Zero external dependencies.**
JDK only: Swing for UI, StAX + `java.util.zip` for XLSX, hand-written SVG for charts. No Maven/Gradle artifacts, ever.
*Why:* the production machine is a locked-down corporate Windows workstation; auditability requires that every line of I/O is in the repository.

**GR-02 — Windows is the production environment; Linux is only the build sandbox.**
- Configuration files are read with a raw line parser, never `Properties.load` (it eats single backslashes in paths like `C:\Users\...`).
- Command-line arguments are de-quoted before use (Eclipse's Arguments box passes quotes through).
- Text exports (KOBRA and similar) default to ISO-8859-1; all generated artifacts are UTF-8.
- Every build is smoke-tested with Windows-style paths before delivery.

**GR-03 — Windows dialogs must be visible and mortal.**
Any dialog: always-on-top owner, a console line announcing that it opened, and `dispose()` on close so the JVM exits. A modal dialog behind the IDE is indistinguishable from a hang; a surviving Swing thread is indistinguishable from a stuck computation. Both happened; neither may happen again.
*Gate (rev 2):* a dialog smoke test in the delivery checklist — open every prompt the build can raise, confirm it is announced on the console, and confirm the JVM exits within a bounded time after it closes. Capability is probed by exercising it, never by asking a flag (R17).

---

## B. Interface and GUI

**GR-04 — The artifact browser is a permanent contractual component.**
The Swing browser (the equivalent of R's `View()` over every intermediate object: par rates, discount factors, forwards, monthly grid, loan frames, notionals, decisions, backtest, hedge series) ships in **every** build. Interactive inspectability is part of the source system's observable behavior — R users can open any object at any moment — so removing the browser is a loss of migrated functionality, not a simplification.
- Simplification passes may simplify the *front door* (how the program is launched). They may never delete the browser.
- A build delivered without the browser is a `GR-04 VIOLATION`, surfaced at S6 like any other divergence.
- Browser tables read through to live objects (lazy rows), filter, sort, and export the filtered view to CSV.

*Link to R10 (rev 2).* GR-04 states this loss qualitatively; R10's graph diff **measures** it. Every
node present only on the source side is either materialised and browsable here, or catalogued as a
deliberate fusion naming the observability given up. The two rules are one property at two
resolutions, and neither discharges the other.

**GR-05 — Figures are shown in the GUI, not only written to disk.**
Every chart exists as a render-neutral model rendered **twice from the same model**:
1. a Java2D panel in a *Figures* section of the artifact browser (zero-dependency — no SVG rendering library is needed because we draw the model directly), and
2. an SVG file in `evidence/<run>/figures/`.
The user must be able to see every figure inside the running program, exactly as an R user sees plots appear in the session.

**GR-06 — Every visual carries its data.**
Each figure writes a companion CSV plus a digest. Equivalence is compared on the data, never on pixels. A layered figure (plot + lines + legend) is one visual, not several.

**GR-14 — Interface parity ceiling.**
The target's launch interface may not be more complex than the source's. The R original takes three file paths; therefore the Java program takes three paths — as arguments, as remembered picker choices, or as properties — and nothing else is required. Role machinery, templates and invalidation logic stay behind that door, invisible unless the user goes looking.

**GR-15 — Configuration round-trips preserve human content.**
Saving configuration rewrites only the changed values and preserves every comment and formatting choice. Regenerating a config file destroys documentation the first time the program writes to it.
*Gate (rev 2):* a round-trip assertion in the delivery checklist — count total lines, comment lines and unrelated settings before and after a save; only the owned values may differ. Migration #1's surgical writer was verified exactly this way (112 lines, 76 comments, 6 settings, unchanged).

---

## C. Input handling

**GR-07 — Content-based anchoring, never positional assumptions.**
Workbook layout is detected by content: instrument columns by label prefix, header rows by the numeric magnitude of their values, date columns by parse plausibility. Fixed row/column indices are forbidden in target code (they are precisely the class of source defect that produced P02/P08). The detected layout is reported (`layoutNote`) **with its margin** (R5) and guarded by preconditions, including date plausibility (a header misread collapses dates to 1899 — P18 exists because it happened).

**GR-08 — No silent loss.**
Every parse reports read / excluded / failed counts that reconcile to the input total. Arguments that don't resolve to an existing file are named with the reason ("no such file — check for a typo, a moved file, or a stray quote"), never silently ignored with a fallback. Duplicate keys are counted and reported, not deduplicated quietly.

**GR-09 — Stream large inputs into primitive arrays.**
The portfolio export is ~865k rows. Parsing streams directly into typed primitive arrays; no intermediate boxed collections or String tables for bulk data. Budget: the full pipeline completes within a 2 GB heap. An out-of-memory crash on real data is a build defect, not a data problem.
*Gate (rev 2):* the delivery checklist requires one end-to-end run on **full-size real input under the declared heap** (`-Xmx` as stated in the build settings, read from them, per R13). A build that has only ever run on a sample has not exercised this rule. Measured baseline: killed at stage 1 → 39 s complete, same 2 GB heap.

**GR-10 — Progress output for long stages.**
Any stage that can exceed a few seconds on real data (the backtest walks ~3,900 observation dates) prints progress with counts and percentage. Silence is indistinguishable from a hang.

---

## D. Numerics and verification

**GR-11 — IEEE-754 `double` throughout.**
Match R's numeric semantics exactly: binary doubles, R's rounding behavior where the source rounds, no `BigDecimal` unless the source genuinely uses decimal semantics.
*Clause (rev 2) — computation and serialisation are different layers.* This rule governs **computation**: R has no decimal type, so decimal arithmetic in the target would diverge from the source, not improve on it. It does **not** govern **serialisation**: canonical digests still render values through rounded decimal at a contracted scale, because a digest must be reproducible across runtimes whose last-ulp accumulation differs legitimately. Compute in `double` to match the source; serialise through rounded decimal to compare. Neither substitutes for the other.
*Gate (rev 2):* a source scan in the delivery checklist rejecting `BigDecimal` in computation paths, with serialisation utilities on a declared allow-list.

**GR-12 — Findings are documented, not fixed.**
A defect discovered in the source becomes a numbered precondition (Pxx, continuing the existing register — currently through P21) with the source's actual behavior faithfully reproduced and the finding reported as evidence. Domain decisions (e.g. two contradictory decision rules) are decided by the owner, never by an agent. This preserves the information barrier: the Java agent implements observed behavior; the Controller reports anomalies.
Each finding also carries its **quantified delta** — the target run both ways on real data (R9).

**GR-13 — Self-tests verify by inversion, not by expected constants.**
Bootstrap is checked by re-deriving par rates from the discount factors; the spline is checked at its knots; the minimum-variance hedge is checked as a local minimum. Tests survive data changes because they test mathematical properties, not memorized numbers. Diagnostic statistics must themselves be validated for robustness (`median(abs(steps))`, not `abs(median(steps))` — the latter collapses at curve turning points and fires false positives). SelfTest must be green before any packaging, **and must run at the declared language level** (R13).
Inversion shares its assumptions with the code it tests (R8); those blind spots are enumerated and covered by structurally different checks.

---

## E. Evidence and change discipline

**GR-16 — Artifacts are immutable and provenance-versioned.**
Cache validity is decided by hash/provenance, never by file timestamp. The provenance fingerprint covers the **entire effective configuration**, not a hand-picked subset — a chosen subset silently recreates the hole that timestamps left. Every run writes its own `evidence/<run-id>/` bundle: checkpoints, preconditions, verdict, run report, figures with backing data.

**GR-17 — Every delivered build is complete; no contractual component may regress.**
Even mid-migration, each delivered build compiles, passes SelfTest, contains the artifact browser (GR-04) with figures (GR-05), and runs end-to-end on the units migrated so far. A build that removes a previously delivered contractual component is a regression finding, exactly as a numeric divergence would be. The delivery checklist:

```
[ ] compiles at the DECLARED level, read from project settings (GR-01, R13)
[ ] SelfTest green, at the declared level (GR-13)
[ ] runs with Windows-style paths and quoted arguments (GR-02)
[ ] dialog smoke test: every prompt announced on console, JVM exits after close (GR-03)   <- rev 2
[ ] artifact browser present, opens every intermediate of every migrated unit (GR-04)
[ ] figures visible in browser and written as SVG+CSV+digest (GR-05, GR-06)
[ ] parse reconciliation counts printed (GR-08)
[ ] full-size real input run to completion under the declared heap (GR-09)                <- rev 2
[ ] progress output on long stages (GR-10)
[ ] no BigDecimal in computation paths; serialisation utilities allow-listed (GR-11)      <- rev 2
[ ] config round-trip: line/comment/setting counts unchanged, only owned values differ (GR-15)  <- rev 2
[ ] launch interface: three paths, nothing more demanded (GR-14)
[ ] evidence bundle written, every artifact schema-validated (GR-16, R12)
[ ] structural graph differences dispositioned (GR-04 + R10)                              <- rev 2, FULL tier
[ ] project_state.json updated (GR-18)
```

**GR-18 — Cross-conversation continuity.**
The repository carries a `project_state.json` recording: migrated units, active preconditions, open findings awaiting domain decisions, GR checklist status of the last delivered build, the declared tier (CORE/FULL), the last verdict with its cap and any waivers, and the next planned unit. Every conversation starts by reading it; every delivery updates it. Memory summaries are a courtesy; this file is the record.

---

## Amendment procedure

General Rules are versioned with the protocol. Adding a rule requires an empirical trigger (something that actually went wrong or was actually lost); removing one requires the owner's explicit decision. Each rule keeps its number forever — retired rules are marked retired, never renumbered.

**Rev 2 adds no new rule.** It gives four existing rules the enforcement they lacked, links GR-04 to R10, and clarifies GR-11. A rule with no gate is advice wearing the costume of law — and the two rules that cost the most were the two wearing it.
