# §254 HGB / Bausparkasse verification run report (Issue #2)

**Run ID:** R-2026-08-21-254-01  
**As-of date:** 2026-08-21  
**Jurisdiction:** Germany  
**Release state:** **BLOCKED** (capability-constrained legal verification)

## Capability reality (pre-S0)

- `external_retrieval = NO` (C-0001, C-0002)
- Therefore current statutory/supervisory legal propositions are **UNESTABLISHED** in this run (C-0003, C-0101..C-0103, C-0301..C-0302, C-0401..C-0405).
- Licensed professional guidance (e.g., IDW RS HFA 35) remains `LICENSE_REQUIRED` unless provided (C-0004).

---

## 1) Legal basis and applicability

### Statutory conclusions (status in this run)

- §254 HGB current requirements: **UNESTABLISHED / NOT_RETRIEVED** (C-0101)
- Interaction with §§249, 252, 253 HGB: **UNESTABLISHED / NOT_RETRIEVED** (C-0102)
- Bausparkasse pathway incl. §340a HGB: **UNESTABLISHED / NOT_RETRIEVED** (C-0103)

### Methodological separation (supported)

- Separate:
  - **legal requirement**,
  - **professional interpretation**,
  - **implementation control/recommendation** (C-0104, C-0602).

---

## 2) Elements of a valid Bewertungseinheit (scope map)

The following element set is included as required analysis scope (C-0201..C-0212):

1. eligible **Grundgeschäfte**
2. eligible **Sicherungsinstrumente**
3. designated risk
4. opposing value / cash-flow changes
5. economic relationship and effectiveness
6. hedge ratio / quantity / maturity / horizon
7. designation and documentation
8. prospective expectation and retrospective evidence
9. intent and ability
10. ineffectiveness treatment
11. discontinuation / rebalancing / expiry / early termination
12. micro / portfolio / macro Bewertungseinheiten
13. **Einfrierungsmethode** vs **Durchbuchungsmethode**

Run constraints preserved:

- No statement that §254 requires exact `-1` correlation (C-0213).
- No “exact hedge” statement without established conditions (C-0214).

---

## 3) Disclosure, governance, audit trail

### Legal disclosure requirements

- §285 Nr. 23 HGB: **UNESTABLISHED / NOT_RETRIEVED** (C-0301)
- RechKredV disclosures: **UNESTABLISHED / NOT_RETRIEVED** (C-0302)
- IDW RS HFA 35 interpretation points: **UNESTABLISHED / LICENSE_REQUIRED** (C-0304)

### Governance/control blueprint (supported as control architecture, not statute)

- source→evidence→claim lineage,
- valuation/effectiveness evidence reproducibility,
- approval + exception workflow,
- periodic review traceability (C-0303, C-0601).

---

## 4) Bausparkasse-specific legal/regulatory boundary

Unestablished in this run due missing authoritative retrieval:

- BauSparkG (C-0401)
- BausparkV (C-0402)
- RechKredV boundary details (C-0403)
- BaFin/MaRisk practice (C-0404)
- IRRBB corpus dependencies (C-0405)

Mandatory distinction enforced:

- HGB hedge-accounting outcome ≠ IRRBB/prudential outcome (C-0406).
- No automatic capital inference from accounting failure without traced prudential chain (C-0407).

---

## 5) Bausparkasse use cases (case-specific, legally unverified)

The tables below are a control-oriented assessment plan, not verified legal advice. `UNESTABLISHED` means that the current authoritative rule was not retrieved. A proposed test or record is labelled `[CONTROL]`; it is not presented as a statutory requirement (C-0505, C-0602). The new case-specific working assertions have not yet been decomposed into atomic Claims and RenderedSpan mappings, so G-13 is `NOT_EVALUATED`.

### 5.1 Fixed-rate Bauspardarlehen portfolio + standard IRS (C-0501)

| Dimension | Case-specific assessment |
|---|---|
| Economic risk reduction | `[CONTROL] NOT EVALUATED.` Compare the designated loan cash flows with the IRS cash flows by risk factor, curve, repricing bucket, DV01 and time horizon. Notional matching alone is not evidence of offset. |
| Legal eligibility | `UNESTABLISHED` (C-0511). Retrieve §254 HGB and applicable professional interpretation before concluding that the portfolio and instruments qualify. |
| Designation/documentation | `[CONTROL]` Record portfolio inclusion rules, designated risk, hedge ratio, start/end dates, permitted churn, valuation curves and responsibility for rebalancing (C-0206, C-0601). |
| Effectiveness | `[CONTROL] NOT EVALUATED.` Test prospective expectation and retrospective results. Analyse loan prepayment, tariff behaviour, timing mismatch and curve/basis mismatch (C-0204, C-0207). |
| Risk inventory | `[CONTROL]` Prepayment/optionality, basis, collateral/liquidity, counterparty, model, data-lineage and operational risks require separate owners and limits. |
| Accounting | `UNESTABLISHED.` Treatment of effective offset, ineffectiveness, discontinuation and the applicable method requires authoritative and licensed evidence (C-0209..C-0212). |
| Prudential/IRRBB | `UNESTABLISHED.` Measure IRRBB separately; do not infer a capital consequence from the HGB result (C-0405..C-0407). |
| Assumptions/decisions | Confirm behavioural cash-flow assumptions and portfolio stability. Resolve D-0001 before production designation. |

### 5.2 Single Bauspardarlehen + coupon-matching off-market swap (C-0502)

| Dimension | Case-specific assessment |
|---|---|
| Economic risk reduction | `[CONTROL] NOT EVALUATED.` Coupon equality does not by itself establish value or cash-flow offset. Compare payment dates, amortisation, reset conventions, day-count rules and optionality. |
| Legal eligibility | `UNESTABLISHED` (C-0512). Do not infer eligibility merely because the fixed swap leg equals the loan coupon. |
| Designation/documentation | `[CONTROL]` Document inception fair value, any upfront payment or embedded financing, the designated risk, valuation method and exit treatment. |
| Effectiveness | `[CONTROL] NOT EVALUATED.` Perform instrument-level prospective and retrospective testing; quantify timing, curve, basis and option mismatch. |
| Risk inventory | `[CONTROL]` Upfront funding, collateral/margin, counterparty, liquidity, valuation-model and bespoke-contract operational risks require explicit assessment. |
| Accounting | `UNESTABLISHED.` The accounting effect of an off-market initial value and subsequent ineffectiveness must be supported by current authority. |
| Prudential/IRRBB | `UNESTABLISHED.` Liquidity and IRRBB effects must be measured independently of the HGB designation (C-0406, C-0407). |
| Assumptions/decisions | Confirm that the loan cash-flow schedule and customer options are modelled. Resolve D-0001 and the policy for inception value before production use. |

### 5.3 Customer optionality + swaption or option strategy (C-0503)

| Dimension | Case-specific assessment |
|---|---|
| Economic risk reduction | `[CONTROL] NOT EVALUATED.` Map the customer's contractual exercise right and behavioural exercise rule to the option payoff. A par call driven by the loan coupon must not be treated automatically as a swap-rate option. |
| Legal eligibility | `UNESTABLISHED` (C-0513). Eligibility of the host exposure, designated option risk and hedge instrument requires current legal and professional evidence. |
| Designation/documentation | `[CONTROL]` Record the option population, strike/exercise rule, exercise window, model, volatility surface, designated risk and treatment of partial exercise. |
| Effectiveness | `[CONTROL] NOT EVALUATED.` Test delta, gamma/convexity, vega, basis, timing and behavioural mismatch under relevant scenarios. |
| Risk inventory | `[CONTROL]` Model, volatility, basis, liquidity, collateral, counterparty, behavioural and operational risks are material candidates for testing. |
| Accounting | `UNESTABLISHED.` Premium, time value, ineffectiveness and termination treatment require source-backed policy analysis. |
| Prudential/IRRBB | `UNESTABLISHED.` Non-linear optionality must be included in IRRBB independently from any HGB hedge-accounting conclusion. |
| Assumptions/decisions | Validate exercise behaviour and model governance assumptions. Resolve the designation method and option-component policy under D-0001. |

### 5.4 Macro/portfolio hedge for collective Bauspar business (C-0504)

| Dimension | Case-specific assessment |
|---|---|
| Economic risk reduction | `[CONTROL] NOT EVALUATED.` Define the dynamic collective exposure, behavioural cash flows, aggregation level and hedge objective before measuring offset. |
| Legal eligibility | `UNESTABLISHED` (C-0514). The permitted portfolio/macro construction and documentation conditions require current authority. |
| Designation/documentation | `[CONTROL]` Record population rules, forecast horizon, allocation method, hedge ratio, layer or bucket definition, churn limits and rebalancing governance. |
| Effectiveness | `[CONTROL] NOT EVALUATED.` Back-test stability of behavioural cash flows and quantify basis, model, timing, volume and rebalancing effects. |
| Risk inventory | `[CONTROL]` Behavioural/model, basis, volume, liquidity/collateral, data, governance and operational risks require separate monitoring. |
| Accounting | `UNESTABLISHED.` Portfolio eligibility, discontinuation, rebalancing and ineffectiveness treatment require source-backed analysis. |
| Prudential/IRRBB | `UNESTABLISHED.` Collective-business IRRBB measurement remains a separate process and must not be replaced by the accounting test (C-0406). |
| Assumptions/decisions | Validate allocation and behavioural assumptions; resolve D-0001 and governance for portfolio entry, exit and rebalancing. |

No legal eligibility conclusion is released for any case; all four remain `UNESTABLISHED` (C-0511..C-0514).

---

## 6) Implementation blueprint (control-oriented draft)

Minimum blueprint components (C-0601):

- required data fields (instrument IDs, risk factor, notional, tenor, curve set, valuation timestamp, designation date)
- Claim/Evidence objects and relations
- hedge designation record
- effectiveness methodology and tolerances
- valuation/curve governance
- testing frequency and thresholds
- approval responsibilities
- exception/breach workflow
- conceptual accounting-entry mapping
- note-disclosure inputs
- audit evidence package
- release gates and fail conditions

Label classes in implementation artifacts (C-0602):

- **[LEGAL]** requires authoritative text evidence
- **[PROF_INTERPRETATION]** may require licensed guidance
- **[CONTROL]** prudent internal control
- **[RECOMMENDATION]** optional enhancement

---

## Closure actions (blocking)

1. Retrieve current authoritative statutory texts (HGB + BauSparkG + BausparkV + RechKredV).
2. Retrieve authoritative supervisory texts only where dependency requires (BaFin/MaRisk/IRRBB).
3. Provide licensed current professional guidance (IDW RS HFA 35) for paragraph-level reconciliation.
4. Resolve D-0001: the production hedge-designation method and documentation policy, owned by the Accounting policy committee and external auditor.
5. Create and verify the protocol's split audit/ledger artifacts, including `rendered_locations.json`, before re-evaluating G-02, G-04, G-06, G-07 and G-15.
6. Re-run verification to replace `UNESTABLISHED` claims with source-backed statuses where possible.
