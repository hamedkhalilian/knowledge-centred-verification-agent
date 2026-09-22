# STATUS — bauspar-engine-java (OCM run 3, SECOND target)

Second, independent IMPLEMENT of neutral spec `ocm-run-3-bauspar-U01-v1`, in Java,
written without sight of the source and without sight of the first (TypeScript) target.

## Milestones

| # | Milestone | State |
|---|---|---|
| 1 | Skeleton compiles at the DECLARED level, read from `project.properties` (R13) | done |
| 2 | io layer with content-based detection + margins, diffed against the spec (R5/R7) | done |
| 3 | Unit U01 (C0..C27 as far as CORE tier needs) and the checkpoint emitter | done |
| 4 | Figures | **stood down by directive 6** (CORE tier; GR-04/05/06 explicitly not required) |
| 5 | Artifact browser | **stood down by directive 6/7** (no UI; Swing explicitly not to be built) |
| 6 | Self-tests, detector calibration (R18), blind spots (R8) | done |
| 7 | Evidence bundle, schema-validated, byte-stable across runs | done |

## Build

```
./build.sh                    # reads java.level from project.properties, gates, compiles
java -cp bin bauspar.Main <contract-table.csv> [valuation-date] [manifest.json] [--out=DIR]
```

`build.sh` runs two gates before `javac`:
- **GR-11** — `BigDecimal` only in `src/bauspar/CanonicalNumber.java`, scanning code with
  comments stripped (it fired on a comment on its first run; the fix was to scan the right
  thing, and prose mentions are still reported).
- **GR-01** — every `import` resolves to `java.*` / `javax.*`. Zero dependencies.

## Dependency budget

Zero. JDK 21 standard library only. No Maven, no Gradle, no jars, no Swing.
`BigInteger` carries the exact-binary arithmetic that C20 and C22 require, so no
computation path touches `BigDecimal`.

## Shape (GR-09/R11)

Two streaming passes over the contract table; columns held in primitive arrays; no boxed
collection of parsed row objects. 503 staged rows in ~0.08 s; the same shape carries the
45,881 of production.
