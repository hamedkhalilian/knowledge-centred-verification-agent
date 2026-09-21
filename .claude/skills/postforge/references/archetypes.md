# Post archetypes

Four shapes. Each names what it needs from the ledger before it can be
written, so a candidate that cannot be sourced is rejected before drafting
rather than padded during it.

---

## 1. `showcase` — one project, its protocol, its numbers

**Use when** a project is shipped or far enough along that its result is
checkable.

**Requires** a project with at least four `evidence` items, at least one of
which is a magnitude (a count, a ratio, a duration).

**Shape** the full eight moves of the voice profile, unmodified.

**The test it must pass:** could a sceptical reader disagree with something
specific? If every sentence is agreeable, there is no post — the reference
post works because "I fixed none of them" is a position someone will argue
with.

---

## 2. `teaching` — one concept, opened up

**Use when** a study document contains an idea that transfers outside its
field. The subject matter is the vehicle; the transferable structure is the
payload.

**Requires** a project with a distinctive concept — `postforge candidates
--archetype teaching` ranks by concept rarity for exactly this reason.

**Shape** deviates at moves 1 and 4:

- Move 1 opens on the *misconception*, not on the work: a plausible belief,
  stated in the reader's own voice, then the number that breaks it.
  > 2.5% of men die in their 91st year. So a 90-year-old has a 97.5% chance
  > of seeing 91.
  >
  > The real figure is 84%.
- Move 4 becomes two or three *stages of understanding* rather than three
  parallel ideas: the wrong model, why it is wrong, what replaces it.

**The test it must pass:** the reader ends able to spot the same error
somewhere in their own work. State where. A teaching post that stays inside
its source field is a summary, and summaries do not travel.

---

## 3. `autopsy` — one decision, and what it cost

**Use when** a project contains a hard call with a real trade-off, especially
one that looks wrong from outside.

**Requires** a project whose `evidence` records both the decision and its
consequence. A decision with no recorded cost is a preference, not a
trade-off.

**Shape** deviates at moves 2 and 5:

- Move 2 states the case *for the other side*, honestly and at full strength,
  before the case for the decision taken.
- Move 5 names what the decision actually cost. A post that claims a free win
  is not an autopsy.

**Worked seed from the corpus:** `hgb-254-bausparkasse` shipped a verification
run whose headline output was `BLOCKED` — 45 claims, 11 unestablished,
`kcv-validate` passing with no findings while the release still failed. The
decision: report the refusal rather than let the model fill the gap. The cost:
a tool whose first real run produces no legal conclusion.

---

## 4. `bridge` — two projects, one shared structure

The archetype that justifies the whole system. A human reading one project at
a time will not find these; the scorer exists to find them.

**Use when** `postforge bridges --cross-domain-only` returns a pair with a
score clearly above the rest of the field.

**Requires** two projects with no shared domain and at least one shared
concept that is rare in the corpus. The rarity is the point: a concept both
sides already had in common is not a transfer.

**Shape** replaces moves 1–3 entirely:

1. **Two facts, from two worlds, stated flat.** No connective. Let the reader
   feel the distance.
2. **The structural claim.** One sentence naming the shared shape.
3. **The translation table.** Term on one side, term on the other. This is the
   move that makes a bridge post land — it is concrete where the reader
   expects hand-waving.

Moves 4–8 continue as normal, with move 5 drawing evidence from *both*
projects.

**The honesty rule, and it is not optional:** a bridge is a hypothesis. Say
so, in the post. The reference voice already does this — it documents findings
it did not fix. A bridge post claims "these share a structure", never "this
solves that". If the transfer has not been tested, the post says it has not
been tested.

**Worked seed from the corpus:** `efron-survival-prediction` ↔
`bgb-498-consumer-credit`, score 3.758, the only cross-domain pair in the
ledger. Shared concepts: `default-termination`, `early-repayment`,
`optionality`. See `corpus/posts/P-DRAFT-hazard-498.md`.
