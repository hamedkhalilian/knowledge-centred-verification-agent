# Knowledge-Centred Verification Agent

A claim-ledger-first verification system for long legal, regulatory, accounting,
tax, financial, technical, and bilingual documents.

The project separates work that requires judgment from rules that software can
enforce deterministically:

```text
source retrieval + semantic analysis
                 │
                 ▼
            Claim Ledger
                 │
        ┌────────┴────────┐
        ▼                 ▼
 deterministic checks   adversarial review
        │                 │
        └────────┬────────┘
                 ▼
             remediation
                 ▼
           regenerated views
                 ▼
              release gates
```

The governing idea is simple:

> The ledger is the semantic source of truth. Documents are rendered views of
> the ledger.

## Why this exists

A request such as “prepare a complete report on §498 BGB” should not produce a
short paraphrase of the provision or an indiscriminate pile of sources. The
research graph should expand through actual claim dependencies: scope and loan
classification, notice requirements, default consequences, costs, mandatory
law, case law, legislative history, relevant EU law, supervisory material, and
time-sensitive amendments.

Retrieval creates evidence. Agent debate tests reasoning. Neither consensus nor
fluent prose can replace missing evidence.

## Repository map

```text
.github/agents/knowledge-verifier.agent.md  GitHub Copilot custom-agent wrapper
prompts/master_prompt_v2.2.md               versioned verification protocol
schemas/                                    portable JSON Schemas
src/kcv_agent/                              deterministic validator and CLI
tests/                                      executable rule tests
examples/498-bgb/                           dependency-led research example
docs/                                       architecture and release model
```

The agent wrapper is intentionally small. GitHub custom-agent prompts are
limited in size, while the full protocol is a versioned specification that
should be reviewable through normal Git diffs.

## Deterministic rules in the first release

| Rule | Check |
|---|---|
| `V-001` | duplicate Claim IDs |
| `V-003` | dangling claim dependencies |
| `V-004` | cyclic claim dependency graph |
| `V-005` | illegal Claim/Evidence status combination |
| `V-008` | derived claim without a derivation rule |

These checks do not ask an LLM to “reason harder.” They run as code and return
stable, machine-readable findings.

## Install and test

Python 3.11 or newer is required.

```bash
python -m pip install -e '.[test]'
pytest
```

Validate a ledger:

```bash
kcv-validate examples/498-bgb/claim-ledger.example.json
kcv-validate --json examples/498-bgb/claim-ledger.example.json
```

The command exits with status `0` when no error-level finding exists and `1`
otherwise.

## Use the GitHub custom agent

After the agent profile is merged into the default branch:

1. Open GitHub Copilot Agents for this repository.
2. Select **knowledge-verifier**.
3. Give it the source document, requested deliverables, as-of date, and scope.
4. Inspect the capability declaration before trusting any verification claim.

The profile first reads `prompts/master_prompt_v2.2.md`, declares its actual
capabilities, builds or updates the claim ledger, runs deterministic validation,
remediates fixable findings, regenerates affected outputs, and reports the
release state.

## Capability honesty

GitHub's cloud agent can read, search, edit, execute, and use repository-scoped
GitHub tools. Arbitrary external web research is not automatically available.
Until an authoritative retrieval MCP server is configured, the agent must state
`external_retrieval = NO` and must not imply that it checked current law.

User-supplied authoritative primary material may still be verified as supplied,
but currentness or supersession remains a separate claim that needs adequate
evidence.

## Project status

This is an early executable foundation, not legal advice and not yet a complete
legal-retrieval product. The next major component is an MCP retrieval layer for
authoritative sources such as Gesetze im Internet, EUR-Lex, BaFin, Bundesbank,
EBA, ECB, and court databases.

## Contributing

Changes to the protocol, schemas, validators, and rendered examples should be
made together when they affect the same invariant. Every new deterministic rule
must have a stable rule ID, documented semantics, and a failing-then-passing
test fixture.

