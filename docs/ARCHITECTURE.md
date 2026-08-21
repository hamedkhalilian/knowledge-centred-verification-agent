# Architecture

## System boundary

The system turns source material and user instructions into an auditable claim
graph. It does not treat a polished document as semantic state.

```text
inputs → segmentation → retrieval → evidence relations → claim ledger
                                                     │
                              ┌──────────────────────┴─────────────┐
                              ▼                                    ▼
                   deterministic validators               semantic review
                              │                                    │
                              └──────────────────────┬─────────────┘
                                                     ▼
                                                remediation
                                                     ▼
                                          dependency propagation
                                                     ▼
                                             regenerated outputs
                                                     ▼
                                                release gates
```

## Main objects

### Run

Records the as-of date, requested artifacts, protocol version, inherited run,
model identifier when known, capabilities, and gate states.

### Claim

An atomic proposition with a stable ID, type, status, rendered spans, dependency
edges, dates, decision conditions, and derivation metadata where applicable.

### Evidence

A source object with provenance and currency metadata. Its stance is not
intrinsic: `AFFIRMS`, `QUALIFIES`, `CONTRADICTS`, or `SILENT` belongs to the
Claim↔Evidence relation because one source can play different roles for
different claims.

### Finding

A rule result with stable rule ID, severity, affected object, message, and
remediation state.

## Separation of responsibilities

| Layer | Responsibility | Typical mechanism |
|---|---|---|
| Retrieval | Obtain authoritative material | legal-retrieval MCP |
| Semantic analysis | Segment and interpret propositions | LLM + protocol |
| Ledger | Hold auditable semantic state | JSON / database |
| Deterministic validation | Enforce graph and state invariants | Python |
| Adversarial review | Challenge reasoning and missing dependencies | LLM pass/agent |
| Regeneration | Render corrected document views | templates/toolchain |
| Release | Apply explicit gates | code + protocol |

## Dependency-led research

Research breadth is justified by claims, not by a generic instruction to collect
many documents. Each new source or legal node should answer a dependency such as
scope, definition, condition, exception, consequence, hierarchy, temporal
validity, or conflict.

## Capability boundary

Capabilities are data, not optimistic assumptions. A run without current
external retrieval may still validate internally derived claims and user-supplied
primary material, but it cannot certify current law without evidence establishing
currency and supersession.

## Evolution path

1. Expand deterministic ledger invariants.
2. Add JSON Schema validation to the CLI.
3. Implement remediation actions as explicit transformations.
4. Add authoritative legal-retrieval MCP adapters.
5. Add reproducible document rendering and visual gates.
6. Persist runs and evidence hashes for incremental verification.

