---
name: postforge
description: Read the user's projects across Google Drive, GitHub, Claude Code sessions and the drop folder, maintain a concept ledger of them, and draft LinkedIn posts in the user's own voice. Use when the user asks to turn their work into LinkedIn content, wants post ideas from their projects, asks what is worth writing about, wants to harvest or re-index their projects, or asks to find connections between things they have worked on.
---

# Post-Forge

Turns a body of work into LinkedIn drafts without flattening it into
marketing copy.

The design follows this repository's governing idea. The **concept ledger**
under `corpus/` is the semantic source of truth about the work; a post is a
**rendered view** of one or more ledger entries. Judgment work — reading a
project, naming its structure, writing prose — is yours. Rules that can be
enforced deterministically live in `src/postforge/` and run as code.

A post may never assert something the ledger's `evidence` does not carry.
That is the one hard constraint, and it is the same constraint the
verification agent in this repository applies to legal claims.

## The five phases

Run only the phases the request needs. "Give me a post about X" is phases
3–5. "What should I write about?" is phases 2–3.

### Phase 1 — Harvest

Read sources and write project records into `corpus/projects/<id>.json`.

| Source | How |
|---|---|
| Google Drive | `search_files` for new material, then `read_file_content`. Record the file ID as `source_ref: drive:<fileId>` |
| GitHub | Read the repository. `source_ref: github:<owner>/<repo>` or `…#path/to/thing` |
| Claude Code sessions | `list_sessions` gives titles and post-turn summaries only, never transcripts. Record what the metadata actually supports and nothing more |
| Drop folder | Read `corpus/drop/*`. This is the only route for anything living in Claude.ai chat Projects, which no connector can reach |

Check `corpus/SOURCES.md` first — it is the queue of known-but-unread
material. Move an entry out of the queue and into a project record only after
actually reading the source.

**Never write a project record for material you have not read.** An
unharvested source belongs in `corpus/SOURCES.md`. Inventing a summary is the
exact failure this repository exists to prevent.

### Phase 2 — Name the concepts

This phase decides whether the system works at all, so slow down here.

**Tag structure, not subject matter.** A concept is a slug naming a
*transferable shape*, not a topic label. Topic labels belong in `domains`.

| Do not write | Write |
|---|---|
| `survival-analysis` | `time-to-first-event`, `hazard-rate`, `censored-data` |
| `german-law` | `undefined-legal-term`, `mandatory-law-boundary` |
| `refactoring` | `observation-vs-correction`, `information-barrier` |

The Efron study and the §498 BGB research map share no subject, no field and
no vocabulary. They bridge because both were tagged `default-termination`,
`early-repayment` and `optionality` — shapes, not topics. Tagged by field
they would never have met.

Reuse an existing slug whenever it fits; run `postforge status` to see the
vocabulary in use. A concept used by one project is invisible to the bridge
detector, and a concept used by every project carries almost no weight.

Fill `evidence` with checkable specifics only: counts, magnitudes, ratios,
named identifiers, measured outcomes. Not adjectives. This list is the
factual budget every future post must draw from.

### Phase 3 — Select

```bash
postforge lint                                  # gate: must pass
postforge status                                # vocabulary and coverage
postforge bridges --cross-domain-only --top 5   # the rare, valuable pairs
postforge candidates --archetype showcase       # evidence-backed projects
postforge candidates --archetype teaching       # distinctive concepts
```

Both selectors already exclude anything a published post covers, so a repeat
does not reach you.

Prefer a cross-domain bridge that scores clearly above the field. That is the
post nobody else can write, because nobody else has both halves. Fall back to
`showcase` or `teaching` when the bridge field is flat.

Bring the user two or three candidates with their scores and one line of
rationale each. Let them pick. Do not draft three posts on spec.

### Phase 4 — Draft

Read `references/voice-profile.md` and `references/archetypes.md` before
writing the first line. Both are short and both are load-bearing.

Write the body to `corpus/posts/<post-id>.md` and the record to
`corpus/posts/<post-id>.json` with `status: "candidate"`.

Post IDs are `P-YYYY-MM-DD-<slug>`.

### Phase 5 — Verify before showing

Check every one of these against the draft:

1. **Every number traces to a ledger `evidence` entry.** Quote the entry if
   asked. A number you cannot trace gets cut, not softened.
2. **No claim beyond what the evidence supports.** A bridge is a hypothesis
   and the post says so.
3. **Voice check** against the banned list in the voice profile.
4. **Length** inside the band `postforge lint` enforces (2,000–2,950).
5. `postforge lint` passes.

Then show the user the draft in full, plus a short note on what it claims and
what it deliberately does not.

## Deterministic rules

`postforge lint` enforces these. They are not advisory.

| Rule | Check |
|---|---|
| `P-000` | malformed project record, or an empty ledger |
| `P-001` | duplicate identifiers |
| `P-002` | a post references an unknown project |
| `P-003` | a post repeats a published post's concept set exactly |
| `P-004` | a `showcase` or `autopsy` post whose sources carry no evidence |
| `P-006` | a concept or domain that is not a lowercase hyphen slug |
| `P-007` | a post body that is missing, or outside the length band |

## What this skill will not do

- Write a post asserting a result the ledger does not evidence.
- Publish anything. It produces drafts; posting is the user's action.
- Summarise a source it has not read.
- Claim a bridge is proven. Bridges are hypotheses until tested.
