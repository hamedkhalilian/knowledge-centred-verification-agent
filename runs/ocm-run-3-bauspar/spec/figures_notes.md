# Figure and geometry notes — unit U01

Companion to `neutral_spec.json`, figure entry `FIG-01`. Everything here is a
fact about how the published geometry is *drawn*, which does not fit the spec's
structured entries. Nothing here is required to reproduce the unit: the unit
computes no picture. It is required to reproduce the *pictures*, and to judge a
figure the way GR-06 requires — **on its backing data, never on pixels**.

The backing object is `customer_export_rows`. Two consumers in the bundle read
it and draw the same figure twice from the same values: a browser page that
emits scalable vector graphics, and a quality harness that draws natively into
a multi-page document. They agree on the geometry below except where noted, and
every disagreement is a finding, not a variant.

---

## 1. What crosses, and what draws

The unit publishes, per contract: five positions on a schematic axis
(`xc`, `xf`, `xa`, `xl`, `xn`), a savings ratio (`sr`), a goal share
(`goal_frac`), four year labels, four amounts, three flags rendered as one and
zero (`warn`, `alloc_est`, `bridge`, and the alarm `special`), a phase and a
contract type. The drawing is entirely a matter of those values; no consumer
re-reads the contract table.

## 2. The canvas

Both consumers use the same numbers, which is why they can be compared at all:

| quantity | value | meaning |
|---|---|---|
| drawing width | 900 | user units |
| drawing height | 500 | user units, and a caption band below it in the harness |
| left edge `x0` | 70 | where the schematic axis position 0 lands |
| right edge `xe` | 830 | where the schematic axis position 1 lands |
| axis line `yax` | 240 | the horizontal baseline the two triangles meet on |
| full height `Hf` | 250 | the height that represents the whole reference amount |

A schematic position `f` is placed at `x0 + f * (xe - x0)`. The vertical scale
is a fraction of the reference amount: `goal = goal_frac * 250`,
`loanref = (1 - goal_frac) * 250`, `sh = sr * 250`, and
`lh = max(0, 1 - sr) * 250`. Heights are measured **upward** from the axis for
saving and **downward** for the loan, which is why the saving triangle is drawn
at `yax - height` and the loan triangle at `yax + height`.

## 3. Substituted defaults — a consumer's, never the unit's

Both consumers substitute a default wherever a published value is missing. These
are **display defaults and they are not the unit's values**; an implementation
of the unit must never adopt them.

| value | substituted when missing | note |
|---|---|---|
| `goal_frac` | 0.40 | same number as the unit's own fallback share, but a different decision |
| `xc` / `xf` / `xa` | 0.02 / 0.06 / 0.40 | the unit's fixed positions, restated |
| `xl` | `xa`, and 0.44 if that is missing too | the unit publishes a missing loan-start position for every saving phase |
| `xn` | 0.30 | |
| `sr` | 0.30 | **a contract with no savings ratio is drawn as if it were at 30 %** |

The last row is worth the operator's attention: a contract whose reference
amount is missing or zero has no savings ratio at all, and both consumers draw
it as an ordinary saver at 30 %. Nothing on the picture says the number is
invented. This is a display defect in the consumers, not in the unit, and it is
recorded here because it is where the unit's missing values become invisible.

## 4. Marks by phase

- **Pale reference, always drawn first.** A saving triangle from `xf` to `xa`
  rising to `goal`, and a loan triangle from `xa` to `xe` falling to `loanref`.
  This is the plan: save to the goal share by allocation, borrow the rest.
- **save** — a filled saving triangle from `xf` to `min(xn, xa)`, rising to
  `min(sh, goal)`. The two minima are the reason a saver's mark never crosses
  the vertex and never overtops the goal line.
- **oversave** — the same triangle drawn twice: once translucent to the full
  `sh`, and once solid but clipped to the goal envelope, so the overshoot is
  visible as a lighter wedge above the goal line. The loan triangle is then
  drawn from `xn`, not from `xa`, and translucently, because over-saving moves
  the vertex right and shrinks the loan. When the warning box is absent, a
  caption gives the smaller loan as a percentage, `round((1 - sr) * 100)`.
- **loan** — the saving triangle is drawn to `sh` and the loan triangle from
  `xa` to `xe`; a solid quadrilateral then fills the loan region from `xa` up to
  `xnc`, where `xnc` is `xn` held inside the interval from `xa` to `xe`, and the
  solid part's right-hand height is `lh * (1 - (xnc - xa) / (xe - xa))`, i.e. it
  tapers with the repayment. The loan triangle starts at the allocation vertex
  even when repayment began later; that is deliberate in both consumers.
- **done** — both triangles at low opacity and the caption "Vertrag
  abgeschlossen" across the middle. No marker.
- **nodata** — a fifth branch, present in both consumers, that the unit never
  reaches: see finding FND-10. It prints "Keine Guthaben-/DaBetrag-Daten".

## 5. Milestones, labels and the goal line

Four ticks on the axis, each with a name below it and the year label below that:
contract start at `xc`, first payment at `xf`, allocation at `xa`, and — only in
the loan and done phases, and only when the loan year label is non-empty — the
repayment start at `xl`. The allocation label carries the unit's tilde prefix
when the date was estimated, so a reader sees `~2029` rather than `2029`; the
tilde is the only signal that a milestone is a guess, and nothing marks an
estimated contract end at all.

The goal line is dashed, drawn at `yax - goal` from `xf` to `xe`, and labelled
at the right with `Sparziel <goal share as a whole percentage> %` plus the goal
amount when one is published. The percentage shown is `round(goal_frac * 100)`,
so a goal share of 0.355 shows as 36 % while the geometry uses 0.355.

## 6. Boxes, and two flags recomputed downstream

- The **red alarm box** at the bottom, "Sonderfall: Bausparsumme > 2x
  DaBetrag", is driven by the published `special` in the browser page, but the
  quality harness **recomputes it** from the published ratio with the same
  cutoff. Same rule, two implementations; finding FND-05 is about the cutoff
  itself.
- The **warning box** at the top, "Bauspardarlehen kaum sinnvoll", is drawn when
  the published `warn` is set **or** the drawn savings ratio is at least 0.90 —
  and the drawn ratio may be the substituted 0.30 of section 3. So the box can
  appear for a contract whose published flag is not set, and the harness's
  caption line prints the published flag separately from the box it drew. There
  is a second, exact way for the two to disagree, and it has nothing to do with
  the substitution: the unit decides the flag on the **unrounded** ratio and
  publishes the ratio **rounded to three places**, so a true ratio of 0.8996 is
  published as 0.900 with the flag not set — and both consumers then draw the
  box. That is finding FND-13, and it is measured, not supposed.

## 7. Caption data in the quality harness

Below each picture the harness prints two lines of the underlying numbers:
balance, loan notional, Bauspar sum, savings ratio as a whole percentage, saving
goal and the loan portion; then the four year labels, the four flags as one and
zero, the goal source, and the goal share to two decimals. Amounts are formatted
with a German thousands **dot** and no decimals. Those caption lines are the
cheapest available check that a picture matches its data, and they are the part
a comparison should reproduce: a figure is compared on its data.

The harness also draws a summary page first: the phase tally, the four flag
counts, the goal-source tally and the contract-type tally, over a seeded random
sample of 100 distinct identifiers taken by **first row per identifier**.

## 8. Palette

Shared by both consumers, listed because a rendered comparison needs it and
because it is data, not judgement: saving `#2BA6A0`, loan `#E08A1E`, plan grey
`#D9DEE5`, plan outline `#B7C0CB`, axis `#5B6B7A`, text `#0F4C5C`, warning
`#C0392B`. Opacities: 0.30 for the oversave overshoot, 0.18 and 0.16 for the
pale loan regions, 0.85 for a saving triangle under a loan, 0.15 for both
triangles in the done phase, 0.08 for a warning box fill.

## 9. What a figure comparison should and should not assert

Compare the backing values, the substituted defaults actually applied, and the
derived heights and positions listed above. Do not compare rendered pixels, do
not compare the scalable-graphics text, and do not treat the two consumers'
different sources for the alarm flag as a divergence of the unit. A layered
picture — plan triangles, filled triangles, goal line, ticks, marker, boxes — is
**one** visual with one backing table, not seven.
