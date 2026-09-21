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
| Claude.ai chats and Projects | No connector reads these. The route is the account's own data export: Settings, Privacy, Export data. It arrives as per-category ZIP archives; run `postforge import-claude <download-folder>`. It writes one digest per conversation and one per Project, with its knowledge docs. Record `source_ref: drop:<filename>` |
| Drop folder | Read `corpus/drop/*` — importer output, plus anything pasted by hand |

Check `corpus/SOURCES.md` first — it is the queue of known-but-unread
material. Move an entry out of the queue and into a project record only after
actually reading the source.

**Never write a project record for material you have not read.** An
unharvested source belongs in `corpus/SOURCES.md`. Inventing a summary is the
exact failure this repository exists to prevent.

`corpus/drop/` is git-ignored apart from its README, because this repository
is public and the digests are verbatim chat transcripts. Never commit one, and
never quote a passage from one into a post without checking what else is in
the sentence.

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

Then fill `friction`, and take it as seriously as the evidence.

Friction is the moment the author was stuck, wrong, or surprised, and what
changed. Evidence is what the work produced; friction is what it cost. This
is the single reason to read chat transcripts at all: Drive already holds the
polished summary and the repository holds the finished code, and only the
transcript holds the turn where someone said "wait, that's wrong".

`postforge import-claude` pre-flags candidate lines from the author's own
turns. They are a shortlist to judge, not a verdict — most are noise, and the
two that are not are worth the whole import. Record friction in the author's
own framing, and keep the original sentence where it is sharp enough to quote.

A project with rich evidence and empty friction produces status updates.

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

### Phase 5 — De-mechanise

A pipeline drifts toward the mechanical, and the drift is invisible from
inside any single post. It shows up across a run of them. Do this pass every
time, on the finished draft, before any checking.

1. **Read the last three published posts first.** If this draft could be
   swapped with one of them and a reader would not notice, it is not ready.
2. **Rotate the opening.** `P-008` blocks a repeat of either of the last two,
   but clearing a rule is not the same as sounding different. Six moves exist:
   `confession`, `misconception`, `two-facts`, `number-first`, `scene`,
   `refusal`.
3. **Cut the scaffolding.** Naming a structure once is fine. `Firstly` /
   `Secondly` / `In conclusion` / `Let me explain why` / `Here's the thing` are
   the seams of a template showing through. Delete them.
4. **At most one post in three has a numbered body.** Otherwise write
   paragraphs. Three numbered ideas is a strong move that stops working the
   moment it becomes the house style.
5. **Carry one friction moment, in the author's own words.** Quote the
   sentence from the transcript where it is sharp. A post where nothing went
   wrong is a report.
6. **Leave one thing unresolved.** Certainty about everything is the clearest
   tell of generated text. The reference post ends on four documented defects
   that were deliberately not fixed.
7. **Do not smooth the phrasing.** The author writes English as a second
   language, bluntly, with em dashes and short reversals. Do not round that
   off into LinkedIn house style. If a sentence in the transcript is awkward
   and exact, awkward and exact beats fluent and generic.
8. **Do not end on a lesson the work did not produce.** If the honest close is
   "I have not tested this", close there.

### Phase 6 — Verify before showing

Check every one of these against the draft:

1. **Every number traces to a ledger `evidence` entry.** Quote the entry if
   asked. A number you cannot trace gets cut, not softened.
2. **No claim beyond what the evidence supports.** A bridge is a hypothesis
   and the post says so.
3. **Voice check** against the banned list in the voice profile.
4. **Length** inside the band `postforge lint` enforces (2,000–2,950).
5. `postforge lint` passes with no blocking finding, and any `P-010` warning
   has been considered rather than ignored.

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
| `P-008` | a post opening the same way as one of the last two published |
| `P-009` | a post citing a friction moment that does not exist |
| `P-010` | a post that cites no friction at all — a warning, not a gate |

## What this skill will not do

- Write a post asserting a result the ledger does not evidence.
- Publish anything. It produces drafts; posting is the user's action.
- Summarise a source it has not read.
- Claim a bridge is proven. Bridges are hypotheses until tested.
- Commit anything out of `corpus/drop/`. The repository is public and those
  files are raw transcripts.
- Produce a run of posts that all sound alike. If the only honest draft this
  week repeats last week's opening, say so and skip a week. Cadence is worth
  less than not being boring.
