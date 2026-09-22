# What run 2 cost — read before starting run 3

Run 2 migrated an 11-file R hedging pipeline to a JDK-only Java/Swing program
under the structural barrier. Final state: 393 of 393 checkpoint objects
byte-identical between an independently executed source and the target;
verdict PROVISIONAL, capped by R2 because the inputs were synthetic
stand-ins. Everything below is what went wrong on the way there.

## 1. The framework shipped without its own artifacts

`ocm_v4.4.zip` says "everything you need is here" and does not contain
`controller.md`, the six JSON schemas, the P01–P21 register definitions, the
canonicalisation contract, an alias map, or migration #1's `project_state.json`.
All were reconstructed. The reconstructions are in `contracts/`; if the
originals exist, they supersede them, and the digests of the two runs are not
comparable until the canonicalisation ids match.

**Fix for v4.5:** ship them, or mark them explicitly as "to be reconstructed
per run" so the reconstruction is a declared step rather than a surprise.

## 2. R3 applies to the spec, not only to the profile

The run's **single** checkpoint divergence was a name list the spec gave as a
count plus constraints instead of as values. Two lists satisfied the
constraints; the implementer necessarily guessed; the guess was wrong. A
mechanical parse of the source had the right values all along and was run too
late to prevent it.

**Fix for v4.5:** make the source detector a mandatory source-side PROFILE
artifact, produced **before** the spec, and gate the spec on a mechanical diff
of every declared name vector against it. `tools/check_detector_vs_spec.py` is
that gate.

## 3. Synthetic observations hardened into contracts

Facts observed in a synthetic stand-in were tagged `observed_in_file` — the
same tag real observations carry. Two invented columns became a contract the
target enforced, and it refused the real workbook, which the source reads
without complaint.

**Fix for v4.5:** split the provenance tag into observed-in-real and
observed-in-synthetic. Never let the two share a label.

## 4. Verification scoped to a bill of materials instead of the behaviour

The target demanded the input's column list *equal* the spec's list. The
source selects the columns it needs by name and ignores the rest. Correct
scope for R7 is the facts the computation depends on; everything else is a
reported difference, not a halt.

## 5. A constant validated only where two readings coincide

An expectation was written relative to the start of a spreadsheet's used
range. On the profiled file the used range began at row 1, so the relative and
absolute readings gave the same number and the error was invisible. On a real
file whose used range began lower, it fired a false halt on sound data — and
the same wrong offset was driving the actual read, which would have taken a
data row as the header. R6, R15 and R18 in one defect.

**Rule of thumb:** express an expectation in the coordinate system the source's
own reader uses, then verify that rule against the reader empirically. Do not
reason about the reader's semantics from its documentation.

## 6. A halt must not cost the operator the work already done

The first build threw away every object built before a halt: no browser, no
evidence bundle. In the source language a script that stops halfway leaves its
workspace intact and the analyst inspects it. That inspectability is migrated
behaviour (GR-04), and losing it on exactly the run where it matters most is a
regression. Halts now keep the partial state, open the browser on it, render
the figures whose data exists, and write a bundle marked incomplete — with no
checkpoint file, because a partial one is not comparable (R12).

## 7. Two controller detectors cried wolf

A label-column heuristic scored raw text distinctness and returned margin 0 on
sound data, because the file stored numbers as text. A source-syntax scanner
matched a for-in pattern against a Java variable named `in`. Both were R18
failures in the controller's own tooling: written for the defect they were
meant to catch, never exercised on known-good input.

## 8. An agent reported a check it had not performed

A "byte-identical" claim covered four fields of a structure, not the
structure; the controller's own diff found a fifth field had changed. The
check was sound, the summary was not.

**Rule:** the controller executes every gate itself. An agent's report of a
green check is not a green check.

---

# Pre-flight for run 3 — what the kit itself was carrying

Found by exercising the kit's own tools on a *different* known-good source
before starting run 3, which is the check finding 7 says the controller's
tooling never gets. All four are fixed in this copy; they are recorded because
the fix matters less than the pattern.

## 9. The kit shipped run 2's answers after promising not to

The README states the kit "deliberately does NOT carry the source code or the
outputs of any previous run: a kit that ships last run's answers cannot test
anything." Five files carried them anyway:

- `contracts/alias_map.json` — 12 entries of run 2's module names.
- `contracts/run_params.json` — run 2's invoked analyses and valuation dates.
- `tools/render_graphs.py` — `ORDER = ["U01"…"U11"]` at module level, and the
  string `OCM v4.4 run 2` baked into every rendered SVG footer, which would
  have stamped run 2's identity onto run 3's evidence.
- `tools/check_detector_vs_spec.py` — one hard-coded source filename and three
  hard-coded group/constant pairs.
- `tools/r_source_detector.R` — `RSD-KOBRA-*` findings naming specific fields,
  and `RSD-DECISION-*` regexes matching run 2's decision phrases.

A stated policy that nothing enforces is a wish, exactly as R21's prohibition
is a wish until `scan_barrier.py` checks it. The contracts are now empty stubs
that declare their own shape, the tools take their per-run names from those
stubs, and a test asserts no tool contains a previous run's identifiers.

## 10. The R3 gate — finding 2's own fix — passed vacuously

Pointed at any source other than run 2's, `check_detector_vs_spec.py` found no
rows for `bsv_loan_overview.R`, compared `None` against `None` three times,
printed three `AGREE`s, and exited 0. It then printed
`catalogue (80 names) ... agreed 393/393 on both sides` — a run-2 result, as a
literal, from a gate that had compared nothing. That is finding 8 (an agent
reporting a check it had not performed) inside the controller's own tool, and
finding 7 (a detector never exercised on different known-good input) in the
tool finding 2 asked for.

Demonstrated, not theorised: the real Bauspar source produces an empty
`r_source_field_groups.csv` — correctly, it has no literal column vectors — and
the old gate reported green on it.

**Rule:** "could not compare" must never share an exit code with "compared and
agreed". The gate now distinguishes 0 / 1 / 2, and every path that once
produced a vacuous 0 now produces 2.

## 11. The mandatory PROFILE artifact halted on ordinary R

`r_source_detector.R` crashed with `argument "dv" is missing, with no default`
on any file containing a function with a non-defaulted parameter — which is
nearly every real R file. The cause is precise and instructive: a formal with
no default holds R's *empty symbol*; `dv <- form[[nm]]` binds a local to it,
and touching that local raises the missing-argument error. So the guard on the
very next line, `if (is.symbol(dv) && ...)`, could never execute. It was
unreachable code that looked like a working defence.

The emptiness has to be tested **in place**, before any binding:
`if (identical(form[[nm]], quote(expr = ))) next`.

**Rule of thumb, extending finding 5:** verify the guard fires, not merely that
it is written. A guard positioned after the operation it protects reads as
correct and defends nothing.

## 12. The detector's silence was indistinguishable from a clean source

With run 2's hard-coded probes removed, the detector would have reported no
anchor and no phrase findings on run 3 — the same output it produces for a
source that genuinely has none. Per-run probes are now declared in
`contracts/source_probes.csv`, and when none are declared the detector records
`RSD-NO-PROBES` naming the path it looked in. A declared probe that cannot be
evaluated reports `RSD-ANCHOR-NO-LAYOUT` or `*-ABSENT` rather than vanishing.

**Rule:** a detector must be able to say "I did not look", in the artifact, in
a form the controller can read. Absence of findings is not a finding of
absence.

## 13. Two "tools" were one run's scripts wearing the kit's name

`tools/profile_inputs.py` and `tools/gen_synthetic.py` sat beside the genuinely
reusable tools, named as if general. Both are run 2's: the profiler hard-codes
that run's filenames, sheet names and assumptions UA-01..UA-03; the generator
produces EUR swap curves on a 1899-12-30 spreadsheet epoch. Neither profiles
nor generates anything for a different source.

Profiling and synthetic generation **are** irreducibly source-specific — that
is not the defect. The defect is shipping them unmarked in the directory a
controller reaches into for general tools, so the natural move is to run them,
get output, and believe a mandatory state has been satisfied. Both now live
under `tools/examples/` behind an EXAMPLE ONLY header naming the run they
belong to.

## 14. Lesson 3's own fix had never been applied

Finding 3 above says: split the provenance tag, never let a synthetic
observation share a label with a real one. `neutral_spec_schema.json` still
carried the single `observed_in_file` enum, and the source agent's brief still
instructed agents to use it. The lesson was written down and then not wired
into the artifact that enforces it.

The enum is now `observed_in_real_input` / `observed_in_synthetic_input` /
`source_code_declared` / `assumption`, and `observed_in_file` is deliberately
rejected rather than deprecated — a still-accepted label is a label that gets
used.

**Rule:** a lesson that lives only in the lessons file is a lesson the next run
repays. Each finding here should name the artifact that now makes it
mechanical, or say plainly that nothing does.

## 15. Not fixed, recorded: the barrier scanner is R→Java shaped

`tools/scan_barrier.py` carries a negative lookbehind for `Boolean.TRUE` /
`Boolean.FALSE`, adjudicated in run 2 because the target was Java. Against a
different target language that exclusion is inert rather than wrong, so it is
left in place — but it is a run-2 adjudication sitting in a general tool, and
the next target language will need its own pass. The scanner's R patterns are
deliberate: this kit's source side is R, as the layout says.
