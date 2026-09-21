# Voice profile — Hamed, English LinkedIn

Derived from one published post, `corpus/posts/P-2026-08-27-ocm.md`. It is a
small sample, so treat this as a description to match, not a template to fill.
When a rule here fights the material, the material wins.

## The shape

Eight moves, in order. A post may drop move 6, never moves 1, 2 or 7.

1. **Concrete opening with a number, then a reversal.**
   A flat first-person statement of what was done, carrying at least one hard
   figure. Then a short paragraph that contradicts the expectation the first
   one set, ending in a two- or three-word sentence.

   > I recently migrated a financial analysis system from R to Java — swap
   > curve bootstrapping, hedge analytics, a loan portfolio with 865,000
   > contracts. Along the way I found four real bugs in the original code.
   >
   > I fixed none of them. On purpose.

2. **Name the trap.** Generalise from the specific case to the failure mode the
   reader also has. Opens with something like "Here's the trap in every X".
   This is where the reader recognises themselves.

3. **Name the thing.** Give the approach a proper noun. A named protocol is
   quotable and memorable in a way a described one is not.

4. **Three numbered ideas.** Each gets a short title line, then two to four
   sentences, and closes on a compressed line that earns its own beat.

   > If the Java side can't peek at the R side, it can't inherit its habits —
   > or its bugs.

5. **The evidence run.** A paragraph of hard, checkable specifics in short
   sentences, deliberately unadorned. This is the paragraph that makes the post
   credible; without it the post is an opinion.

6. **The craft aside** (optional). "A few engineering choices I'm fond of:" —
   a single sentence of technical decisions. Signals care without claiming
   superiority.

7. **The close.** "What stuck with me:" followed by a two-clause antithesis
   where the second clause reverses the first.

   > The Java code was the deliverable. The evidence trail was the value.

8. **Five to six hashtags.** PascalCase, on one line. Mix two or three broad
   tags with two or three that only the right reader searches.

## Mechanics

| Property | Value |
|---|---|
| Length | 2,000–2,950 characters; the reference post is 2,812. LinkedIn hard-caps at 3,000 |
| Person | First person singular. Never the corporate "we" |
| Paragraphs | One to four sentences, blank line between every one |
| Em dashes | Frequent, for apposition and for the turn in a sentence |
| Numbers | Digits, with units and context: "865,000 contracts", "~70x" |
| Identifiers | Real ones, unexplained: P08, P21, V-024, §246(2) |
| Emoji | None |
| Questions to the reader | None. No "Thoughts?", no "What do you think?" |

## Register

- States limits as facts, not as modesty. "None fixed" is a decision with a
  reason, not an apology.
- Prefers the concrete noun to the abstract one: "a hand-written XLSX reader
  on the JDK's zip and StAX", not "a lightweight parsing layer".
- Explains a term exactly once, at first use, in a clause — never in a
  parenthesis that interrupts the sentence.
- Credits the method, not the author. The post is about what held up, not
  about how hard it was.
- Allows one aesthetic judgement per post ("choices I'm fond of"), no more.

## Friction is not optional

The reference post works because of four sentences most writers would cut:

> And real data did violate them. […] All documented, none fixed — because
> changing production logic is a business decision that deserves a human
> signature, not a silent edit inside a rewrite.

That is the author admitting the work found problems it chose not to solve. It
is the most quotable passage in the post and the only one that risks anything.

Every draft carries at least one such moment, taken from the ledger's
`friction` list and cited in the post record's `friction_refs`. Where the
author's own sentence from a transcript is sharp, quote it rather than
paraphrasing — a second-language sentence that is blunt and exact reads more
human than a fluent one that is neither.

## Banned

These break the voice on contact:

`Excited to announce` · `Thrilled to share` · `game-changer` · `leverage`
(as a verb) · `deep dive` · `unlock` · `journey` · `Here's why 👇` ·
`Thoughts?` · `Agree?` · a rhetorical question as the first line · emoji ·
one-sentence-per-line formatting · a numbered list where each item is a
fragment · claiming a result the evidence in the ledger does not support.

The last one is the only one that is a correctness bug rather than a style
bug. A post may not assert something the source project's `evidence` list
does not carry. If the sentence needs a number that is not in the ledger,
either go and verify it or cut the sentence.
