# Migration Operating Protocol — v4.4

**Supersedes:** v4.3 (and the v4 amendments draft, v4.1, v4.2). Incorporates an
external audit of v4.3 which found one missing enforcement point, four rules
with no gate, one unclosed structural finding, an undefined scaling rule, and
two precision defects — plus two owner decisions recorded in §7.

**Audience:** an agent executing a source-to-target migration. You have no
access to the session that produced this. Everything you need is here.

**Status of each rule:** every rule carries the evidence that produced it. A rule
with no evidence line was not earned and should be treated as advice, not law.

**Tier:** every rule is marked **[CORE]** or **[FULL]**.
- **CORE** applies to every migration regardless of size. These are rules whose
  omission caused real damage and whose cost is near zero.
- **FULL** applies to high-stakes work: regulated, long-lived, financially
  material, or maintained by someone other than its author.
- The tier is chosen by the owner **before** implementation begins and recorded
  in the verdict. Choosing CORE-only is legitimate; discovering afterwards that
  you were CORE-only is not.

---

## 0. How to use this document

Rules are **binding**. Each has a TRIGGER (when it applies), an ACTION (what you
must do), and a STOP (what halts the run). A STOP is not a warning; it ends the
current state and returns to an earlier one.

Where a rule can be checked by a program, the check is named. **Prefer running
the check over satisfying yourself that you complied.** The single most repeated
error in the record below is an agent reading a contract, believing it complied,
and never executing the validator that would have said otherwise. It happened
three times: with source comments, with a schema, and with a compiler level.

### Verdict vocabulary

Four verdicts, in decreasing strength. The verdict is a fact about the evidence,
never about confidence.

| Verdict | Means |
|---|---|
| `APPROVE` | every required layer ran, evidence complete both sides, barrier enforced |
| `VERIFIED_TARGET_ONLY` | the target satisfies its contracts, but no independent source-side execution, or the barrier was not structural |
| `PROVISIONAL` | no real inputs yet; positional constants are unverified assumptions |
| `BLOCKED` | required evidence is impossible to obtain; state exactly which |

A waiver may raise nothing. It records that the owner accepted a named risk; the
verdict stays where the evidence puts it.

---

## 1. Binding rules

### R1 — Observed data is the only evidence  **[CORE]**

**TRIGGER:** you are about to write any constant describing an input: a header
row count, a column offset, a field index, a sheet name, a delimiter, an encoding.

**ACTION:** cite an observation of the actual file. Record the observation in the
input profile.

**STOP:** if the constant's only source is a comment, a docstring, a variable
name, or a specification document, you may not write it as a constant. Register
it as an unverified assumption and mark the output PROVISIONAL.

**EVIDENCE:** a source comment read `col A = Instrument`. The instruments were in
column B; column A was blank. The comment was not careless — the source's own
reader begins at the first used cell, so the blank column was **unobservable from
inside the source system**. Every layout constant transcribed from that comment
was wrong in the same direction. Cost: four round trips.

**GENERALISATION:** a system cannot observe the layer it abstracts over. Enumerate
every normalisation the source's readers perform — first-used-cell, type
coercion, header inference, whitespace trimming, encoding detection, silent
missing-value coercion — and profile precisely those seams with a tool that does
not perform them.

---

### R2 — The input profile is not skippable  **[CORE]**

**TRIGGER:** entering implementation.

**ACTION:** the profile must exist and must record, for every touched field:
actual type, null count, **minimum and maximum**, categories, encoding,
duplicates, and row × field counts.

**STOP:** if real inputs are unavailable, you may proceed but must (a) mark every
output PROVISIONAL, (b) register every positional constant as an unverified
assumption with an executable precondition, (c) cap the run verdict at
PROVISIONAL, and (d) re-enter profiling the first time real inputs appear,
before any result is interpreted.

**EVIDENCE:** the protocol already required this. Two words — "when available" —
made skipping frictionless, and it was skipped silently. Six of ten failures in
the record were preventable by profiling first.

---

### R3 — Ranges, not shapes  **[CORE]**

**TRIGGER:** recording any field in the profile.

**ACTION:** record minimum and maximum. For small structurally decisive vectors
(maturities, group keys, level sets) record **the values themselves**, not their
count.

**STOP:** a profile with counts and no ranges does not satisfy R2.

**EVIDENCE:** a value row was read as the date header. The evidence looked
perfect: 171 columns, 171 dates parsed, zero unreadable headers, every count as
expected. Only the range was absurd — every date landed on the spreadsheet epoch,
because a rate of 2.25 is a valid day number. **No count could detect this.**
Min and max detect it instantly.

For key vectors: "35 maturities" carries no information. `1..30, 35, 40, 45, 50,
60` tells you the bootstrap miscounts coupons past the thirty-year point.

---

### R4 — Plausibility, not parseability — at every layer  **[CORE]**

**TRIGGER:** writing any precondition about a value being readable, parseable, or
computed without error.

**ACTION:** add a companion precondition on the plausible RANGE or SHAPE. This
applies to inputs **and to derived quantities**: forward curves, weights summing
to one, ratios expected near unity, monotone factors.

**STOP:** a "was readable" precondition alone does not discharge R4.

**EVIDENCE, inputs:** the precondition "every observation-date header was readable
as a calendar date" **passed** on the run where all 171 dates were wrong. True
and useless.

**EVIDENCE, derived quantities:** a smooth par curve with gapped maturities
produced forwards `28Y=3.023, 29Y=3.005, 30Y=2.989, 35Y=3.556`. A monotone
decline reversing by +0.57pp exactly at the first gap. Implemented as a
precondition it reports:

```
FAIL  at maturity 35 the forward moves +0.5341 pp against a typical
      recent step of -0.0175 pp (32x)
```

**The statistic must be deviation from LOCAL TREND, not raw step size.**
Legitimate short-end curvature produces steps of the same magnitude as the
artefact (0.41 against 0.57 — overlapping). Against the median of recent steps
the separation is clean: 32× artefact against 5× real curvature, threshold at
10×.

---

### R5 — Detect layout by content, and report the margin  **[CORE]**

**TRIGGER:** locating any anchor in an input.

**ACTION:** find anchors by what they contain. Report the winning score, the
runner-up, and the gap.

**STOP:** below a declared margin the layout is AMBIGUOUS. Halt and ask. Do not
proceed on a coin flip.

**EVIDENCE:** the first header-row heuristic chose the wrong row by **one cell out
of thirty-six** and reported it with the same confidence as a correct answer.
Only a conflict with an independent reading exposed it. With margin reporting:

```
labels in column B, dates on row 6  [column 35 vs 0, margin 35; row 57 vs 1, margin 56]
```

is a usable signal. `labels in column B` is not.

---

### R6 — Any number that came from one file is an example, not a constant  **[CORE]**

**TRIGGER:** writing a threshold, separator, or limit into the protocol or the
implementation.

**ACTION:** derive it from the profile at run time, or declare it an example.

**STOP:** a magic number with a single-file provenance may not become a rule.

**EVIDENCE:** this rule exists because an earlier draft violated R1 twice.
"A date serial has five figures, a rate has at most two" was promoted from one
observation to a rule — it fails on basis-point conventions, rates stored as
fractions, text dates, and observation dates predating the fifth digit. Same for
a row-count threshold governing memory strategy. Both are now worked examples;
the rules underneath are *report the magnitude distribution so the separator is
chosen from data*, and *declare the memory strategy as a function of profiled
row × field count*.

---

### R7 — Do not let one implementation configure the other  **[CORE]**

**TRIGGER:** you have a source-side observation and are tempted to transfer it as
target configuration.

**ACTION:** observations cross as **expectations to verify**, never as settings to
adopt. The target performs its own detection regardless, then compares:
agree → proceed and record the agreement as evidence; disagree → halt and report
both; source silent → target proceeds on its own detection, flagged.

**STOP:** transferring semantics — tenor alignment rules, threshold meaning,
coupon frequency, decision direction — is forbidden in all cases. Only facts
about files may cross.

**EVIDENCE:** two independent readings both reported "labels in column B, dates on
row 6." That agreement was real evidence. Under auto-configuration it would have
been tautological — and it would have concealed the R5 defect above.

Live illustration: the source's bootstrap miscounts coupons where maturities are
gapped. Auto-configuration would have carried that defect into the target and
made it permanently invisible. It was found only because the target held an
independent opinion and stated it.

**Depends on R21.** Inside one context this rule is unenforceable by
construction — it becomes an intention, not a control.

---

### R8 — A test that shares an assumption with the code cannot test that assumption  **[CORE]**

**TRIGGER:** designing any verification.

**ACTION:** for each test, enumerate the assumptions it shares with the code under
test. Those are its blind spots. Cover each with a structurally different check.

**STOP:** a suite whose blind spots are not enumerated is not a suite.

**EVIDENCE:** the bootstrap was verified by inversion — feed the factors back
through the par-swap identity, recover the input rates. It passes to ~1e-15
**including on the curve where the coupon count is wrong**, because the test
shares that count with the recursion.

**CORRECTION TO AN EARLIER DRAFT:** that draft claimed "no output test can detect
this; only inspecting the input can." **False.** A test built on a different model
does detect it — see R4's forward-curve check. Input inspection remains cheapest
and most certain; the derived-quantity check is the backstop for assumptions
nobody thought to profile.

---

### R9 — Flag, do not repair  **[CORE]**

**TRIGGER:** you find behaviour in the source that appears defective.

**ACTION:** catalogue it with an executable precondition. **Quantify it by running
the target both ways on real data** and reporting the delta. Present the decision
to the operator.

**STOP:** you may not correct it without explicit instruction. When instructed,
implement the correction as a **named, configurable policy** with the original
behaviour reachable by one setting, so comparison against the source remains
possible.

**EVIDENCE:** four defects had been silently producing wrong numbers for years.
None produced an error. All four would have been carried into the target by any
equivalence-driven translation, and its tests would have passed.

Quantification is cheap by construction: both code paths already exist — the
faithful one was built, the corrected one is the fix under consideration. It
converts a list of findings into a decision-ready memo, and it answers the
question the owner actually has: *since when, and how wrong?*

**This is the rule with the highest expected value and the one most in tension
with mainstream practice.** Functional-equivalence validation is structurally
incapable of detecting source defects: if the acceptance criterion is "matches
the old system," a faithful translation of a defect passes.

---

### R10 — Structure is verified separately from values  **[FULL]**

**TRIGGER:** claiming the migration is faithful.

**ACTION:** build the data-flow graph of both sides — nodes are modules and
published objects, edges are PRODUCE and READ — and diff them. Reconcile naming
through a **single declared alias map** so a rename cannot masquerade as a
structural difference.

**CLOSURE (new in v4.4):** a graph diff that produces a number nobody must act on
is decoration. Every node present on one side only is dispositioned:

- **source-only node** → either (a) materialised in the target and reachable in
  the artifact browser (GR-04), or (b) catalogued as a deliberate fusion, naming
  the reason and **the observability that was lost**;
- **target-only node** → justified as a required intermediate, or removed;
- every disposition is recorded in the evidence bundle.

**STOP:** an undispositioned structural difference blocks APPROVE.

**EVIDENCE:** checkpoints ask whether the same numbers appear at the same points.
They cannot see whether the same structure produced them: two pipelines can agree
on every digest while one has fused stages, dropped an intermediate, or reversed
a dependency.

Measured on migration #1:

```
             source                 target
nodes        18 (11 mod, 7 obj)     12 (7 mod, 5 obj)
edges        26                     12
depth        3                      2
```

Three objects exist only on the source side; two only on the target. The numbers
agree; the **observability** does not. Invisible to every value-based test — and
it is the same loss GR-04 forbids qualitatively, measured quantitatively.

---

### R11 — Scale and liveness are shape properties  **[CORE]**

**TRIGGER:** any input above roughly 10^5 rows, or any stage whose duration scales
with input size.

**ACTION:** stream rather than materialise; never hold two full representations at
once; numeric columns in primitive arrays; categorical columns interned; dates as
epoch day numbers. Long stages emit periodic progress.

**STOP:** a run that appears frozen must be distinguishable from one that is slow.

**EVIDENCE:** an 865,524-row × 80-field export was held twice — once as parsed
string arrays, again as the boxed typed table built from them. Near the heap
ceiling the collector thrashes and the process appears frozen: no error, no
output, indistinguishable from slow computation. Measured: killed at stage 1
under a 2 GB heap → complete run in **39 seconds** under the same heap.

The 10^5 figure is an example, not a limit (R6). Declare the memory strategy as a
function of profiled row × field count.

---

### R12 — Validate every artifact against its schema, every run  **[CORE]**

**TRIGGER:** emitting any evidence artifact.

**ACTION:** run a schema validator. Not a review — a validator.

**STOP:** an artifact that does not validate is not evidence.

**EVIDENCE — the most embarrassing entry in this record.** The checkpoint bundle
was claimed schema-conformant for an entire migration and had **135 validation
errors**. Four distinct contract violations, every one a real defect in
comparability:

- `digest` was a bare string; the contract requires the **algorithm and
  canonicalisation** to travel with the value. Two runs whose digests differ but
  whose canonicalisation also differs have not been compared at all.
- `probes` was a map; the contract requires an array carrying a
  **`selection_rule`**. A probe value without the rule for choosing the row
  cannot be reproduced on the other side.
- `coverage` omitted untracked fields; the contract requires all five present as
  null. An absent field and a tracked zero are different claims.
- Three root fields the contract forbids.

The bundles could not have been diffed against a source-side bundle. Nobody would
have noticed until the comparison was attempted and produced nothing.

---

### R13 — Test at the DECLARED level, not the convenient one  **[CORE]**

**TRIGGER:** compiling, running, or validating anything that has a declared
target: a language level, a schema version, a runtime, an encoding.

**ACTION:** execute against the declared level. Read the level from the project's
own configuration so the two cannot drift apart.

**STOP:** a green build at a level the project did not declare is not a green
build.

**EVIDENCE:** `Thread.threadId()` is a Java 19 method. The project declared Java
17 compliance. Every sandbox build used a bare compiler on a Java 21 runtime,
which compiled it happily against its own newer API surface. The failure appeared
only on the operator's machine, at run time, as:

```
java.lang.Error: Unresolved compilation problem:
    The method threadId() is undefined for the type Thread
```

The IDE was correct throughout. The build that had been called clean for the
whole project had never once run at the level the project declared.

**GENERALISATION — this is the same failure three times over.** Constants were
read from comments instead of from files. Conformance was read from a schema
instead of from a validator. A build was run at a convenient level instead of the
declared one. In each case an authority was consulted where an execution was
required. **Prefer the execution. Always.**

Practical form: a build script that reads the level from the project settings.

```bash
LEVEL=$(grep -oP 'compliance=\K[0-9]+' .settings/org.eclipse.jdt.core.prefs)
javac --release "$LEVEL" -Xlint:all -d bin $(find src -name "*.java")
```

---

### R14 — A detector must derive its explanation from evidence  **[FULL]**

**TRIGGER:** writing any check that reports a cause, not merely a fact.

**ACTION:** work the cause out from the data at the point of the finding.

**STOP:** a hard-coded explanation may not be printed as though it were measured.

**EVIDENCE:** a forward-curve check was written to catch one cause — maturities
treated as consecutive when they are not — and printed that sentence for every
anomaly it ever found. On real data it fired at maturity 21, where the maturities
*are* consecutive and the node came from supplied data. The finding was real; the
explanation was false, and it was printed with the authority of a measurement.

A detector that always gives the same explanation is guessing in the voice of a
result. Corrected, the same check now asks three questions of the data — is there
a gap at this node, was this node interpolated, is it supplied and consecutive —
and reports a different cause and a different **severity** for each:

```
gapped, non-consecutive   FAIL     recursion counts the wrong coupons here
interpolated node         FAIL     the fill is oscillating, not smoothing
supplied and consecutive  FLAGGED  a feature of the par curve, not a defect
```

**Corollary on severity.** FAIL means structurally wrong. FLAGGED means unusual
and worth a look. Collapsing the two teaches the operator to ignore both.

---

### R15 — A threshold calibrated on synthetic data is not calibrated  **[CORE]**

**TRIGGER:** any tolerance, ratio limit or cutoff chosen while testing against
generated data.

**ACTION:** re-validate it against real data before it governs a verdict. Report
the observed distribution so the limit can be judged.

**STOP:** a limit that has only ever seen smooth synthetic input may not produce
a FAIL on real input until it has seen real input.

**EVIDENCE:** an anomaly ratio limit of 8x separated artefact from noise cleanly
on analytic curves — 30x against 1.5x. Real market curves are rougher: a genuine
liquidity-driven bend produced 13.3x and tripped a limit that had never seen a
real curve. This is R6 applied to a number derived from synthetic data rather
than from one file, and it is the same error.

---

### R16 — Never decline an input in silence  **[CORE]**

**TRIGGER:** the program is about to ignore, skip, drop, or fall back from
anything the operator supplied — an argument, a path, a column, a row, a file.

**ACTION:** name it and say why, in one line, before continuing.

**STOP:** a silent fallback is a defect regardless of whether the fallback is
correct.

**EVIDENCE — four separate failures, one cause.**

*Arguments.* Three file paths were supplied. One had a missing extension. The
program tested `isRegularFile`, found nothing, **said nothing**, fell through to
its configuration, found the same wrong path there, and opened a file picker. The
operator saw a dialog and no explanation. The correct behaviour is one line:

```
These arguments did not resolve to an existing file:
  C:\...\kobra202412   (no such file)
```

*Configuration.* A path file was read with a parser that treats a backslash as an
escape. `C:\Users\me\file` silently became `C:Usersmefile`. No error — the path
simply "did not exist", and the run fell back to substitute data. The parser was
replaced with one that takes the value as written; the general rule is that **a
format whose failure mode is silent corruption is the wrong format** for a field a
human types.

*Reporting order.* Path-invalidation notes were printed before the resolution
that produces them, so the list was always empty and a wrong path produced no
diagnostic at all. **A diagnostic generated by an operation cannot be reported
before that operation runs** — check the ordering, not just the presence.

*Display.* A truncated preview limit was printed as though it were the size of
the data: a 47,382-row sheet reported as 400 rows. Any figure narrowed by a
budget must say so at the point it is shown.

---

### R17 — Probe a capability; do not ask whether it exists  **[CORE]**

**TRIGGER:** branching on any environment capability — a display, a terminal, a
network path, a file permission, an optional dependency.

**ACTION:** exercise the capability. Treat the attempt as the test.

**STOP:** a boolean that reports configuration is not evidence of capability.

**EVIDENCE:** `GraphicsEnvironment.isHeadless()` returned **false** on a machine
whose display connection then threw on the first dialog. It reports whether the
runtime is *configured* for headless operation, not whether a display answers. It
returns false in a remote session without forwarding, and in a container with a
stale display variable. Trusting it means announcing a file picker and then
crashing.

The repair is to enumerate the screen devices, which forces the connection that
would otherwise fail later, at a point where failing is harmless.

**Corollary — an interactive prompt must be unable to hang an unattended run.**
A modal dialog with no owner window can open *behind* the IDE. It is modal, so
the program blocks on something the operator cannot see, which is
indistinguishable from a hang and is the worst failure an input prompt can have.
Give the dialog an always-on-top owner, announce it on the console, and provide a
setting that disables prompting entirely for scheduled runs.

---

### R18 — A false positive costs what a miss costs  **[FULL]**

**TRIGGER:** any check that can produce a verdict.

**ACTION:** before it is allowed to FAIL, run it against input known to be
**good** as well as input known to be bad. Report the separation between the two.

**STOP:** a check that has only ever been tested on the defect it was written for
is not calibrated. See also R15.

**EVIDENCE — twice in one session.**

A forward-curve check written to catch one cause printed that cause for every
anomaly it found. On real data it fired at a maturity where the structure was
sound, and reported a genuine market feature as a bootstrap defect.

An input investigator applied a date-header heuristic to an ordinary data table,
where five-figure contract numbers look exactly like date serials, and announced
`IMPLAUSIBLE — a rate row was probably read as the header`. There was no date
header; the sheet had none. The fix was to require a real count — ten or more
date-like values in a row — before claiming to have found one.

**A detector that cries wolf trains the operator to dismiss it, and the next
warning it raises will be the one that mattered.** That cost is not smaller than
a miss; it is the same cost, deferred and harder to trace.

---

### R19 — When you write to a file a human edits, edit it  **[CORE]**

**TRIGGER:** the program persists anything into a file a person maintains.

**ACTION:** rewrite only the lines you own. Copy comments, blank lines, ordering
and unrelated keys through untouched.

**STOP:** regenerating such a file is destruction, not writing.

**EVIDENCE:** a configuration writer would have replaced a documented file —
seventy-six comment lines and six format settings — with four bare key-value
pairs, the first time the program saved anything. The surgical version was
verified by counting: 112 lines, 76 comments and 6 settings before and after,
with only the four owned values changed.

A file that quietly loses its own documentation the first time a program writes
to it is not a file anyone will trust to hold anything.

---

### R20 — Incomplete evidence caps the verdict  **[CORE]**  *(new in v4.4)*

**TRIGGER:** any evidence bundle carrying `complete: false`, an
`observer.mode: STATIC` on the source side, a verification layer that did not
run, or a required artifact that did not validate.

**ACTION:** record, in the verdict itself and not in prose, **which observation is
absent and what it would have covered**.

**STOP:** the verdict may not exceed `VERIFIED_TARGET_ONLY`. `APPROVE` requires
both: source-side **execution** evidence, and a structural barrier (R21). An
owner's written waiver may accept the risk; it does not raise the verdict.

**EVIDENCE:** R2 already caps the verdict when real inputs are missing. There was
no equivalent rule for missing *observation*, so a unit could reach APPROVE on
target-only evidence while the controller's own founding principle — incomplete
evidence can localise a problem but cannot alone approve equivalence — had no
enforcement point anywhere in the document. Migration #1 ran with
`observer.mode: STATIC, complete: false` and nothing stopped it.

**NOTE — two different things are often bundled as "source-side observation".
Separate them, because their cost differs by an order of magnitude:**

| | What it is | Cost | Required for APPROVE |
|---|---|---|---|
| **(a) Source execution** | actually run the source and emit checkpoints under the shared canonicalisation contract | low — an interpreter and a script | **yes** |
| **(b) Source instrumentation** | full static+dynamic tracing of the source (flow manifest, mutation metadata, effect interception) | high — a tool to build and maintain | **no** (FULL tier) |

(a) is what makes a comparison real: it is the only thing that turns "the target
satisfies its contracts" into "the two implementations agree". (b) buys mainly
the flow graph, which **R10 already produces without it**. A migration that does
(a) and defers (b) with a recorded waiver is in a defensible position. One that
does neither is verifying the target against itself.

---

### R21 — The barrier is structural or it is not a barrier  **[CORE]**  *(new in v4.4)*

**TRIGGER:** assigning the controller, source-agent and target-agent roles.

**ACTION:** run the source agent and the target agent in **separate contexts**.
Only files cross between them: the neutral specification, the contracts, the
schemas. The controller is the only role that sees both sides, and it sanitises
everything that crosses.

**STOP:** roles sharing one context cap the verdict at `VERIFIED_TARGET_ONLY`
(R20), and the sharing must be named in the verdict — not left to be inferred.

**EVIDENCE:** migration #1 ran all three roles in one context. The neutral spec
was *provably* free of source syntax — but it was written by an agent that had
read the source, so its freedom from syntax says nothing about its freedom from
the source's framing. No discipline inside one context substitutes for
separation.

The counter-example is measured: in a controlled slice with genuinely separate
contexts, the two sides produced **byte-identical SHA-256 checkpoint digests**
having never seen each other's values. That agreement is evidence precisely
because neither could see the other's answer. Under shared context the same
result would have been unfalsifiable.

Separation costs nothing to build — the artifacts that make it possible already
exist. It is an organisational choice, not an engineering task, which is why it
is CORE despite protecting a FULL-tier property.

---

## 2. Required artifacts

| Artifact | State | Schema | Must validate | Tier |
|---|---|---|---|---|
| `input_profile.json` | PROFILE | `input_profile_schema.json` | yes | CORE |
| `neutral_spec.json` | SPECIFY | `neutral_spec_schema.json` | yes | CORE |
| `checkpoints_source.json` | OBSERVE_SOURCE | `checkpoint_schema.json` | yes | CORE |
| `checkpoints_target.json` | OBSERVE_TARGET | `checkpoint_schema.json` | yes | CORE |
| `verdict.json` | COMPARE | `verdict_schema.json` | yes | CORE |
| `flow_manifest.json` | DISCOVER + PROFILE | `flow_manifest_schema.json` | yes | FULL |
| `runtime_trace.json` | OBSERVE_TARGET | `runtime_trace_schema.json` | yes | FULL |
| `graph_source.svg` / `graph_target.svg` | VERIFY | — | rendered, diffed, **dispositioned (R10)** | FULL |

`checkpoints_source.json` is listed separately from `checkpoints_target.json`
deliberately. v4.3 listed one `checkpoints.json` and its verification ladder
claimed checkpoints had caught "value divergence and its location" — but §6 of
the same document stated no source-side observation had occurred. Divergence from
what? Two files, two states, two producers: the ambiguity cannot recur.

### The barrier is enforced mechanically or not at all

The spec generator must (a) drop any field the schema marks source-side-only, and
(b) scan the finished artifact for source-language syntax and **fail the build**
on any hit.

**Validate the detector by injecting a leak.** A detector that has never fired is
not known to work. On migration #1 an injected line —
`comfortable <- sapply(valuation_by_year, function(df) sum(df$DaBetrag, na.rm=TRUE))`
— fired four patterns simultaneously. A clean scan then means something.

Mechanical scanning is necessary and **not sufficient**: it proves the absence of
syntax, never the absence of framing. That is what R21 is for.

---

## 3. The verification ladder

**Twelve layers.** Each has a demonstrated catch and a demonstrated blind spot.
None subsumes another.

| # | Layer | Tier | Caught, on real data | Blind to |
|---|---|---|---|---|
| 1 | Input profile | CORE | blank leading column; formula/value concatenation; epoch collapse; row scale | semantics |
| 2 | Barrier scan | CORE | 4 syntax patterns on an injected leak | framing, correctness |
| 3 | Preconditions (23) | CORE | tenor gaps; 25-year block; duplicate keys; spread range 226× grid | value drift |
| 4 | Target checkpoints, cross-run | CORE | non-determinism; regression between builds | anything the target gets consistently wrong |
| 5 | **Source↔target checkpoint comparison** | CORE | value divergence **and its location** | structural fusion |
| 6 | Inversion self-tests (43) | CORE | bootstrap, spline, min-variance, statistics | assumptions it shares |
| 7 | Derived-quantity plausibility | CORE | the gap defect independently, 32× vs 5× | input shape |
| 8 | Schema validation | CORE | 135 contract errors in own output | semantics |
| 9 | Build at declared level | CORE | a Java 19 method in a Java 17 project | runtime behaviour |
| 10 | Good-input control run | FULL | 2 detectors that cried wolf on sound data | defects the detector was not written for |
| 11 | Runtime trace | FULL | exceptions with type and message; effects; completeness | values |
| 12 | Graph comparison | FULL | 3 source-only and 2 target-only objects | values |

Layers 4 and 5 were one row in v4.3, which is how a target-only comparison came
to be described as if it had a source side. **Layer 5 requires R20(a).** Without
it, layer 5 did not run, and R20 caps the verdict.

**Use this table as the acceptance criterion.** A migration is verified when every
layer of the declared tier has run and each has either passed or produced a
catalogued finding.

---

## 4. Findings ledger

What to expect to find. All four survived years in production without producing a
single error.

| # | Finding | Detected by | Magnitude |
|---|---|---|---|
| 1 | Curve maturities not consecutive | P08 structural; P19 forward plausibility | every discount factor beyond 30Y wrong |
| 2 | Book outgrew a hard-coded row block | P12 structural | the source script now raises |
| 3 | Percent treated as decimal in payoff | P20 domain | payoffs 100× in currency terms |
| 4 | Threshold grid far below observed range | P21 data | grid 226× too narrow |

**R9 obligation:** for each, run the target both ways and report the numeric delta
on real data. Both code paths exist by construction. This converts a list into a
decision-ready memo, and it is cheap.

---

## 5. The measured record

The evidence base for everything above. **N = 2 migrations.** Treat as a
replicated observation, not a result.

| Defect class | Share |
|---|---|
| Mathematics / algorithm | **0** — bootstrap, spline, hedge ratio, statistics correct from first compile, never changed |
| Input shape, layout, encoding, scale | 6 of 10 |
| Environment / harness | 4 of 10 |

**Invert the default planning assumption: budget the input layer as the main body
of work and the mathematics as the cheap part.** Most planning does the opposite.

---

## 6. What is not established

State these limits in the verdict, not in prose.

**N = 2.** Two migrations, different domains. Strong enough to invert a planning
assumption; not strong enough to be called a result.

**Source instrumentation (R20(b)) has never been performed.** Flow-graph figures
come from static analysis and an independent target run. Deferred by owner
decision — see §7 — with R10 covering the graph in its place.

**These rules are engineering methodology, not theory.** The individual ideas are
established: differential testing; design by contract; clean-room
reimplementation; program dependence graphs; data profiling. The contribution is
the synthesis for migration, with the evidence bundle as the unit of account —
and the empirical claim in §5.

**Resolved since v4.3:** the barrier is no longer a matter of discipline (R21),
and missing evidence can no longer pass unnoticed (R20).

---

## 7. Owner decisions on record

| Decision | Choice | Consequence |
|---|---|---|
| Structural barrier | **CLOSE** — source and target agents run in separate contexts from the next migration | R21 becomes binding; agreement between sides becomes admissible evidence |
| Source-side execution — R20(a) | **CLOSE** — the source is executed and emits checkpoints under the shared canonicalisation contract | layer 5 of the ladder becomes available; APPROVE becomes reachable |
| Source instrumentation — R20(b) | **WAIVE**, recorded | Flowtrace deferred. Accepted risk: no dynamic source-side effect interception or mutation metadata; mitigated by R10 (graph), R4 (derived-quantity plausibility) and layer 5 |

Rationale for the split, since it is the least obvious decision here: (a) is
cheap and is the thing that makes a comparison real; (b) is expensive and its
principal unique output is the flow graph, which R10 already produces. Reliability
per unit of effort is maximised by taking (a) and deferring (b).

---

## 8. Pre-flight checklist

Before writing one line of reader code:

- [ ] Tier declared (CORE or FULL) and recorded in the verdict
- [ ] Real inputs obtained, or every output marked PROVISIONAL
- [ ] Profile complete: types, nulls, **ranges**, categories, encoding, duplicates, row × field counts
- [ ] Key vectors captured **in full**
- [ ] Every positional constant traced to an observation, not a comment
- [ ] Every date field given a plausible-range precondition
- [ ] Every derived quantity with a known shape given a plausibility precondition
- [ ] Layout anchors detected by content, **with margins reported**
- [ ] Memory strategy declared as a function of profiled size
- [ ] Source and target agents in **separate contexts** (R21), or the verdict capped and the sharing named
- [ ] Source execution planned so layer 5 can run (R20a), or waived on record
- [ ] Barrier detector validated by injecting a leak
- [ ] Schema validator wired into the run, not into a review
- [ ] Blind spots of every test enumerated
- [ ] Build runs at the level the project declares, read from its own settings
- [ ] Every detector's explanation derived from data, not hard-coded
- [ ] Every threshold re-validated against real data before it can FAIL
- [ ] FAIL and FLAGGED kept distinct
- [ ] Every check run against KNOWN-GOOD input before it may FAIL
- [ ] Nothing supplied by the operator is ever declined in silence
- [ ] Capabilities probed by exercising them, not by asking a flag
- [ ] Diagnostics reported AFTER the operation that generates them
- [ ] Any figure narrowed by a budget says so where it is shown
- [ ] Human-edited files are edited, never regenerated
- [ ] FULL tier only: both graphs rendered, diffed, and **every difference dispositioned**

---

## 9. Build this first

A standalone input investigator, before the pipeline. It is the concrete form of
the profile rule and it settles the entire input layer in one pass.

**Must not use the source language's convenience readers.** They normalise away
exactly the anomalies being hunted.

**Delimited text:** line count and the *distribution* of field counts. A ragged
file is where positional readers mis-assign silently.

**Spreadsheets:** every sheet name; the true grid at real coordinates; text cells
per column (finds the label column); and per row, a count of date-like against
rate-like values separated by magnitude. Report the detected date range and flag
an implausible one.

**Key vectors:** the actual values, any gaps, and what a gap costs.

---

## Changelog: v4.3 → v4.4

| Change | Origin |
|---|---|
| **R20** — incomplete evidence caps the verdict; source execution and source instrumentation separated | audit F1: R2 capped for missing inputs, nothing capped for missing observation |
| **R21** — the barrier must be structural | audit F2: all three roles shared one context, declared but uncontrolled |
| **R10 closure rule** — every structural difference dispositioned, linked to GR-04 | audit F4: the diff produced a number nobody was obliged to act on |
| **CORE / FULL tiers** on every rule and artifact | audit F5: a protocol with no defined minimum is abandoned rather than scaled |
| Verdict vocabulary defined; waivers cannot raise a verdict | required by R20 |
| Ladder split into 12 layers; target-only and source↔target comparison separated | audit F6 + the "nine layers / eleven rows" defect |
| `checkpoints_source.json` and `checkpoints_target.json` listed separately | same root cause as above |
| R9 quantification obligation moved into the rule's ACTION | it was an obligation buried in §4 |
| §7 owner decisions on record | v4.3 had no place to record a decision |

Rules keep their numbers forever. Nothing was renumbered or removed.
