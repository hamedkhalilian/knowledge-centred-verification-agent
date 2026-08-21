# Repository instructions

## Source of truth

- Treat the claim ledger as semantic state and generated documents as views.
- Treat `prompts/master_prompt_v2.2.md` as the governing protocol for v2.2.
- Never silently weaken `must`, `may`, `should`, conditions, exceptions, dates,
  numerical thresholds, citations, or evidence status.
- Do not represent a human decision, assumption, or unresolved branch as a fact.

## Capability discipline

- Declare capabilities before a verification run.
- Do not claim that external retrieval, compilation, rendering, or isolated audit
  occurred unless the environment actually performed it.
- If authoritative external retrieval is unavailable, label the gap explicitly.

## Code changes

- Deterministic rules live in `src/kcv_agent/validator.py`.
- Keep rule identifiers stable once released.
- Add or update tests for each rule change.
- Keep schemas aligned with the Python model and examples.
- Prefer standard-library code unless a dependency has a clear operational need.

## Required checks

Run before proposing a change:

```bash
python -m pip install -e '.[test]'
pytest
kcv-validate examples/498-bgb/claim-ledger.example.json
```

## Pull requests

Explain whether the change affects the protocol, ledger schema, deterministic
rules, remediation, release gates, or documentation. Identify any capability
that was not available during verification.

