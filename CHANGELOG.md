# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and releases use [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Post-Forge: a concept-ledger-first generator for LinkedIn drafts, applying
  the repository's ledger-and-rendered-view model to a second problem domain.
- `postforge` CLI with `lint`, `status`, `bridges`, and `candidates`.
- Deterministic rules P-000, P-001, P-002, P-003, P-004, P-006, P-007.
- Cross-project bridge scoring over concept rarity, domain distance, and
  evidence density.
- `corpus/` concept ledger seeded with six harvested projects, one published
  post, and one bridge draft.
- `postforge` Claude Code skill with a voice profile and four post archetypes.
- Thirty-two tests for the new rules and the scorer.
- `postforge lint` added to the CI gate.
- `postforge import-claude`, which unpacks a Claude.ai data export into
  per-conversation digests. This is the only route to Claude.ai chats and
  Projects, which no connector reads.
- A `friction` field on project records, recording where the work went wrong,
  alongside `evidence`, which records what it produced.
- Anti-formula rules P-008 (opening-move rotation across recent posts), P-009
  (cited friction must resolve), and P-010 (a warning when a post cites none).
- A de-mechanise phase in the skill, and a closed vocabulary of six opening
  moves.
- `corpus/drop/` git-ignored apart from its README: this repository is public
  and the digests are verbatim transcripts.

## [0.1.0] - 2026-08-21

### Added

- Repository-level GitHub Copilot custom agent.
- Versioned knowledge-centred verification protocol v2.2.
- Claim, Finding, and Run JSON Schemas.
- Dependency-free Python validator and `kcv-validate` CLI.
- Deterministic rules V-000, V-001, V-003, V-004, V-005, V-006D, V-008,
  and the Claim-level portion of V-024.
- Seventeen regression tests, including a 3,000-node dependency-chain test.
- Dependency-led §498 BGB example with explicit capability limitations.
- Architecture, release-model, and GitHub-agent operating documentation.

[Unreleased]: https://github.com/hamedkhalilian/knowledge-centred-verification-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hamedkhalilian/knowledge-centred-verification-agent/releases/tag/v0.1.0
