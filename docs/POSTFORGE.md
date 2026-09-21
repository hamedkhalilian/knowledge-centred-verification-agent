# Post-Forge — projects to LinkedIn drafts

Post-Forge reads a body of work spread across Google Drive, GitHub, Claude
Code sessions and a drop folder, keeps a **concept ledger** of it, and drafts
LinkedIn posts from that ledger in the author's own voice.

It reuses this repository's governing idea rather than inventing a new one:

> The ledger is the semantic source of truth. Posts are rendered views of the
> ledger.

```text
Drive · GitHub · sessions · drop folder
                 │
                 ▼  harvest (agent judgment)
          concept ledger  ──  corpus/projects/*.json
                 │
        ┌────────┴────────┐
        ▼                 ▼
 deterministic rules   bridge scoring     ──  src/postforge/
  (P-000 … P-007)      (rarity × distance)
        │                 │
        └────────┬────────┘
                 ▼
          post candidates
                 ▼  draft against the voice profile
           corpus/posts/*.md
```

## Why a ledger and not a prompt

Asking a model to "write a LinkedIn post about my project" regenerates an
opinion each time. It cannot tell you that you have already published this,
that a claim has no evidence behind it, or that two of your projects share a
structure you have not noticed.

Those three questions are decidable, so they are code:

| Question | Answered by |
|---|---|
| Have I already posted this? | `P-003`, plus candidate filtering |
| Does this claim have evidence? | `P-004`, plus the `evidence` list |
| Which two projects secretly connect? | `postforge bridges` |

## The interesting part: bridge scoring

Summarising one project is easy and cheap. The question worth machine time is
which **pair** of unrelated projects shares a structure.

Each pair that shares a concept scores on three factors:

- **rarity** — smoothed inverse document frequency over the shared concepts. A
  concept every project has is worth almost nothing; a concept exactly two
  projects have is worth a lot. Rarity is the whole signal, because a bridge
  is interesting in proportion to how little the two sides were already
  connected.
- **domain distance** — `1.0` for disjoint domains, `0.5` for partial overlap,
  `0.2` for identical. Two statistics projects sharing a statistics concept is
  not a transfer of ideas.
- **evidence** — `0.5 + 0.5 × density`, saturating at six evidence items
  across the pair.

On the shipped corpus this ranks the study of Efron's survival chapter against
the §498 BGB research map at **3.758**, half again as high as anything else
and the only cross-domain pair in the ledger. Shared concepts:
`default-termination`, `early-repayment`, `optionality`. The resulting draft
is `corpus/posts/P-2026-09-21-hazard-498.md`.

### The rule that makes it work

Concepts must name **structure**, not subject matter. Subject matter goes in
`domains`.

| Do not write | Write |
|---|---|
| `survival-analysis` | `time-to-first-event`, `hazard-rate`, `censored-data` |
| `german-law` | `undefined-legal-term`, `mandatory-law-boundary` |
| `refactoring` | `observation-vs-correction`, `information-barrier` |

Tagged by field, a statistics paper and a consumer-credit provision never
meet. Tagged by structure, they collide immediately.

## Commands

```bash
postforge status                                # vocabulary and coverage
postforge lint                                  # deterministic gate, exit 1 on failure
postforge bridges --cross-domain-only --top 5
postforge candidates --archetype showcase
postforge candidates --archetype teaching
postforge --json bridges                        # machine-readable
```

`postforge lint` runs in CI alongside `kcv-validate`.

## Deterministic rules

| Rule | Check |
|---|---|
| `P-000` | malformed project record, unknown source kind or stage, empty ledger |
| `P-001` | duplicate project or post identifiers |
| `P-002` | a post references an unknown project |
| `P-003` | a post repeats a published post's concept set exactly |
| `P-004` | a `showcase` or `autopsy` post whose sources record no evidence |
| `P-006` | a concept or domain that is not a lowercase hyphen slug |
| `P-007` | a post body that is missing, or outside 2,000–2,950 characters |

`P-005` is reserved for a same-domain bridge warning and is not yet emitted;
the `cross_domain` flag on each bridge already carries that information.

The length band in `P-007` is calibrated on the reference post, which runs
2,812 characters against LinkedIn's 3,000-character limit.

## Corpus layout

```text
corpus/
├── projects/*.json     one harvested body of work each
├── posts/*.json        post records; *.md are the bodies
├── drop/               raw material no connector can reach
└── SOURCES.md          the harvest queue: known but not yet read
```

## Capability honesty

The same discipline this repository applies to legal claims applies here.

- There is **no connector for Claude.ai chat Projects.** Anything living only
  there reaches the ledger through `corpus/drop/`, never through automated
  harvest.
- `list_sessions` returns Claude Code session titles and post-turn summaries.
  It does not return transcripts. A session's project record may only record
  what that metadata supports.
- A source that has not been read gets a row in `corpus/SOURCES.md`, not a
  project record. Writing a summary for unread material is the exact failure
  this repository exists to prevent.

## Using the agent

The agent side lives in `.claude/skills/postforge/`:

| File | Contains |
|---|---|
| `SKILL.md` | the five phases, and what the skill refuses to do |
| `references/voice-profile.md` | the eight structural moves, mechanics, banned phrases |
| `references/archetypes.md` | `showcase`, `teaching`, `autopsy`, `bridge` |

Ask for what you want — "what should I post about?", "turn the §254 run into a
post", "find connections between my projects" — and the skill runs only the
phases that request needs.

## Limits

- The voice profile is derived from **one** published post. Treat it as a
  description to match, not a template. It should be re-derived as the corpus
  of published posts grows.
- Bridge scoring only sees concepts that a human actually wrote down. A
  connection nobody tagged is a connection nobody finds.
- A bridge is a hypothesis about shared structure, never a proof that a method
  transfers. Drafts are required to say so in the post itself.
