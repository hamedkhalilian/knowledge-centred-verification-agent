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

## 5) Bausparkasse use cases (structured but legally unverified)

Use cases included (C-0501..C-0504):

1. fixed-rate Bauspardarlehen portfolio + standard IRS
2. single fixed-rate Bauspardarlehen + off-market swap
3. customer optionality + swaption/option strategy
4. macro/portfolio hedge for collective Bauspar business

Per-case analysis dimensions required (C-0505):

- economic risk reduction
- legal eligibility under §254
- designation/documentation
- effectiveness + ineffectiveness drivers
- liquidity/collateral/basis/model/operational risks
- accounting consequences
- prudential/IRRBB consequences
- assumptions and decisions

Current legal eligibility verdict for all four cases: **UNESTABLISHED in this run** (C-0511..C-0514).

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
4. Re-run verification to replace `UNESTABLISHED` claims with source-backed statuses where possible.
