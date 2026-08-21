# Knowledge-Centred Verification Agent

[![CI](https://github.com/hamedkhalilian/knowledge-centred-verification-agent/actions/workflows/validate.yml/badge.svg)](https://github.com/hamedkhalilian/knowledge-centred-verification-agent/actions/workflows/validate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

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

> [!IMPORTANT]
> This is an alpha research and verification framework, not legal advice. A
> passing deterministic gate establishes internal ledger consistency only; it
> does not establish that the underlying legal or technical proposition is true,
> current, or complete.

## Why this exists

A request such as “prepare a complete report on §498 BGB” should not produce a
short paraphrase of the provision or an indiscriminate pile of sources. The
research graph should expand through actual claim dependencies: scope and loan
classification, notice requirements, default consequences, costs, mandatory
law, case law, legislative history, relevant EU law, supervisory material, and
time-sensitive amendments.

Retrieval creates evidence. Agent debate tests reasoning. Neither consensus nor
fluent prose can replace missing evidence.

## Quick start: use it as a GitHub agent

After `v0.1.0` is on `main`:

1. Open [GitHub Copilot Agents](https://github.com/copilot/agents).
2. Select this repository and the `main` branch.
3. Select **knowledge-verifier** from the agent picker.
4. Start with the smoke-test prompt in [the GitHub agent guide](docs/GITHUB_AGENT.md#first-smoke-test-prompt).
5. Inspect the agent's capability declaration before trusting its output.

The full guide also covers source-backed runs, issue assignment, Copilot CLI,
privacy limits, and troubleshooting.

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

## Normative state model

`prompts/master_prompt_v2.2.md` is authoritative. The schemas, validator, tests,
and examples implement its field names and vocabularies:

- `claim_status`: `PENDING`, `SUPPORTED`, `SUPPORTED_CONDITIONAL`,
  `UNESTABLISHED`, `UNSUPPORTED`, `CONTRADICTED`, `OUTDATED`, `UNRESOLVED`
- `evidence_status`: `PRIMARY_VERIFIED`, `AUTHORITATIVE_SECONDARY`,
  `SECONDARY_ONLY`, `LICENSE_REQUIRED`, `NOT_RETRIEVED`, `SOURCE_CONFLICT`
- Claim types: `SOURCE`, `DERIVED`, `INTERPRETIVE`, `DEFINITION`

Assumptions and Decisions are separate protocol entities; they are not Claim
types.

The two Finding producers intentionally use separate contracts:

- `schemas/finding.schema.json` models compact deterministic-validator findings
  (`V-000`, `V-001`, and related executable rules).
- `schemas/protocol-finding.schema.json` models the richer v2.2 review/audit
  Finding object with target, phase, resolution, agent, and provenance fields.

Run-artifact tests validate both models and verify produced paths recorded in
`artifact_manifest.json`. They also validate each semantic-ledger Source and
Evidence object against `schemas/source.schema.json` and
`schemas/evidence.schema.json`, including the protocol's controlled
vocabularies for source kind, access, and retrieval method.

## Deterministic rules in the first release

| Rule | Check |
|---|---|
| `V-000` | malformed Run/Claim structure and an empty ledger |
| `V-001` | duplicate Claim IDs |
| `V-003` | dangling claim dependencies |
| `V-004` | cyclic claim dependency graph |
| `V-005` | illegal `claim_status` × `evidence_status` combination |
| `V-006D` | supported derived conclusion outranks a premise |
| `V-008` | derived claim lacks a rule or at least one premise |
| `V-024` | a `FLAG` matrix cell lacks an explicit Claim qualification |

These checks do not ask an LLM to “reason harder.” They run as code and return
stable, machine-readable findings.

The current executable layer does not yet implement V-010/V-011 because
Assumptions, Decisions, and rendered spans are not yet modelled as validator
inputs. V-024 currently checks the Claim-level qualification; verifying its
presence at every materially assertive rendered occurrence remains future work.
All findings emitted by this release gate are `RELEASE_BLOCKING`;
`INFO`/`WARNING`/`ERROR` are reserved in the finding schema for future
non-gating or layered producers.

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

## GitHub custom-agent behavior

The profile first reads `prompts/master_prompt_v2.2.md`, declares its actual
capabilities, builds or updates the claim ledger, runs deterministic validation,
remediates fixable findings, regenerates affected outputs, and reports the
release state. See [Use the Knowledge Verifier on GitHub](docs/GITHUB_AGENT.md)
for exact activation steps and reusable prompts.

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

## License and citation

Released under the [Apache License 2.0](LICENSE). Citation metadata is available
in [`CITATION.cff`](CITATION.cff), and release history is recorded in
[`CHANGELOG.md`](CHANGELOG.md).
