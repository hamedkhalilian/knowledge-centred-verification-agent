# Crossing ledger — OCM run 3

Every artifact that moves between rooms, in order. R21 barrier: **structural**
— the source agent and the target agent run in separate contexts, and the
target agent never sees the source.

An entry is added when a crossing is *proposed*, and completed when the
controller has scanned and validated it. Nothing crosses unrecorded.

## Quarantine — never crosses

| Artifact | Why |
|---|---|
| `source_room/customers_data.js` | The source's own OUTPUT on real data (45,881 contracts, valuation date 2026-03-31) — the answer key. Crossing it at any point before the target's independent emission would end the run's evidential value (F2). It is also withheld from the **source** agent during SPECIFY: the spec must describe how to compute, and an agent that has read the answers can encode them without meaning to. |
| `source_room/customer_engine_v4.R` | The source itself. |
| `source_room/qa_sample_customers_v4.R` | Source-language downstream harness. |
| `source_room/customer_view_v4.html` | Source-side view. |

## Crossings

| # | When | Artifact | Direction | Barrier scan | Schema | Status |
|---|---|---|---|---|---|---|
| 1 | SPECIFY | `neutral_spec.json` | source → controller | pending | pending | **proposed** |
| 2 | SPECIFY | `flow_manifest_source.json` | source → controller | pending | pending | **proposed** |
| 3 | SPECIFY | `emit_checkpoints.R` | source → controller only | n/a (stays source-side) | n/a | **proposed** |

Crossing 3 is listed because it is produced by the source agent and executed by
the controller, but it does **not** flow to the target: it is the source's own
emitter and is written in the source language by design.

## Controller assertions

- No agent has been spawned before this ledger existed.
- The target room does not exist yet.
- Nothing has crossed source → target.
