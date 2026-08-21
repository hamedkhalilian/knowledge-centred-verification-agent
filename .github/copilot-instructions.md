# Copilot instructions

This repository implements a knowledge-centred verification protocol.

- Read `AGENTS.md` before changing code or protocol files.
- Keep semantic content in the claim ledger; treat prose outputs as rendered
  views that must be regenerated after ledger changes.
- Maintain stable validator rule IDs and deterministic output ordering.
- Do not invent retrieval, execution, compilation, rendering, or audit results.
- Keep `schemas/`, `src/kcv_agent/`, `tests/`, and examples synchronized.
- Run `pytest` and validate the §498 BGB example before completion.

