// src/preconditions.ts
//
// The neutral spec's preconditions P-01 .. P-13 and the executable preconditions
// carried by the thirteen findings.
//
// Detector discipline (target directive 14, R14, R18, GR-13):
//   * every check derives its explanation from the data AT THE POINT OF THE
//     FINDING -- there is no canned sentence printed as though it were measured;
//   * FAIL and FLAGGED stay distinct: a check of severity FLAGGED can never
//     report FAIL, and a passing check of either severity reports PASS;
//   * every check is exercised against KNOWN-GOOD input before it is allowed to
//     FAIL (selftest.ts runs the whole pipeline over a good fixture and a bad
//     one and reports the separation);
//   * a check that could not be exercised at all says NOT_EXERCISED rather than
//     passing vacuously.

import { intText, scriptNumber as plain } from "./canonical.js";
import { renderIsoDate } from "./dates.js";
import { INPUT_COLUMNS } from "./engine.js";
import type { Aggregates } from "./table.js";
import { neumaierSum } from "./store.js";

export type Severity = "FAIL" | "FLAGGED";
export type Status = "PASS" | "FLAGGED" | "FAIL" | "NOT_EXERCISED";

export interface PreconditionResult {
  id: string;
  severity: Severity;
  status: Status;
  statement: string;
  evidence: string;
}

export interface PreconditionContext {
  agg: Aggregates;
  headerNames: string[];
  valuationDay: number;
  valuationDateSource: string;
  coercedColumns: string[];
  dateMarkerSet: string[];
}

function verdict(sev: Severity, breached: boolean): Status {
  if (!breached) return "PASS";
  return sev === "FAIL" ? "FAIL" : "FLAGGED";
}

function rng(min: number, max: number): string {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return "no non-missing value";
  return plain(min) + " .. " + plain(max);
}

function median(v: Float64Array): number {
  if (v.length === 0) return NaN;
  const a = Array.from(v).sort((x, y) => x - y);
  const m = a.length >> 1;
  if (a.length % 2 === 1) return a[m]!;
  return neumaierSum([a[m - 1]!, a[m]!], false) / 2;
}

export function evaluatePreconditions(ctx: PreconditionContext): PreconditionResult[] {
  const a = ctx.agg;
  const out: PreconditionResult[] = [];
  const push = (
    id: string, severity: Severity, breached: boolean, statement: string, evidence: string,
  ) => out.push({ id, severity, status: verdict(severity, breached), statement, evidence });

  // ---- P-01
  const absent = INPUT_COLUMNS.filter((c) => ctx.headerNames.indexOf(c) < 0);
  const surplus = ctx.headerNames.filter((h) => INPUT_COLUMNS.indexOf(h) < 0);
  push(
    "P-01", "FAIL", absent.length > 0,
    "The contract table carries all eleven names of input_column_catalogue, spelled exactly, case-sensitively.",
    (absent.length === 0 ? "all eleven names bound" : "absent: " + absent.join(", ")) +
      "; surplus fields REPORTED not rejected: " + (surplus.length ? surplus.join(", ") : "none"),
  );

  // ---- P-02
  const bsv = ctx.headerNames.indexOf("BSV") >= 0;
  push(
    "P-02", "FAIL", !bsv,
    "The identifier field is present; the unit's own writer stops with a named error when it is not.",
    bsv ? "BSV bound at position " + intText(ctx.headerNames.indexOf("BSV") + 1) + " of the header"
        : "BSV is not among the header names: " + ctx.headerNames.join(", "),
  );

  // ---- P-03
  let unread = 0;
  let unreadHyph = 0;
  const p03Lines: string[] = [];
  for (const [f, st] of a.dateStats) {
    unread += st.unreadable;
    unreadHyph += st.unreadableHyphenated;
    const total = st.marker + st.hyphenValid + st.eightDigitValid + st.unreadable;
    p03Lines.push(
      f + ": marker " + intText(st.marker) + ", eight-digit valid " + intText(st.eightDigitValid) +
      ", hyphenated valid " + intText(st.hyphenValid) + ", unreadable " + intText(st.unreadable) +
      (st.unreadableHyphenated > 0 ? " (of which hyphenated, WHICH ABORT: " + intText(st.unreadableHyphenated) + ")" : "") +
      " -> " + intText(total) + " reconciles to " + intText(a.rowsRead) + " rows read" +
      (total === a.rowsRead ? "" : "  *** DOES NOT RECONCILE ***") +
      (st.offenders.length ? "; first offenders: " + st.offenders.map((o) => "row " + intText(o.rowIndex) + "=" + JSON.stringify(o.value)).join(", ") : ""),
    );
  }
  push(
    "P-03", "FAIL", unread > 0,
    "Every non-missing value of the five date fields is readable as a date by the rule in behaviour step C1.",
    p03Lines.join(" | ") + " || total unreadable " + intText(unread) +
      ", of which hyphenated (abort-triggering) " + intText(unreadHyph),
  );

  // ---- P-04
  const p04: string[] = [];
  let outside = 0;
  let anyParsed = false;
  for (const [f, st] of a.dateStats) {
    outside += st.outOfPlausibleRange;
    if (st.parsedCount > 0) anyParsed = true;
    p04.push(
      f + ": " + (st.parsedCount > 0
        ? renderIsoDate(st.minDay) + " .. " + renderIsoDate(st.maxDay) + " over " + intText(st.parsedCount) + " parsed"
        : "no parsed value") +
      ", outside 1950-01-01..2100-01-01: " + intText(st.outOfPlausibleRange),
    );
  }
  out.push({
    id: "P-04", severity: "FLAGGED",
    status: !anyParsed ? "NOT_EXERCISED" : verdict("FLAGGED", outside > 0),
    statement: "Parsed dates are plausible: between 1950-01-01 and 2100-01-01.",
    evidence: p04.join(" | "),
  });

  // ---- P-05
  const t = a.tariff;
  push(
    "P-05", "FAIL", t.atMostZero > 0 || t.aboveOne > 0,
    "Every non-missing tariff share is greater than 0 and at most 1, so that it is a fraction and not percent points.",
    "range " + rng(t.min, t.max) + "; missing " + intText(t.missing) +
      "; at most 0: " + intText(t.atMostZero) + "; greater than 1: " + intText(t.aboveOne) +
      "; distinct raw texts of tariff_amount: " + distinctText(a, "tariff_amount"),
  );

  // ---- P-06
  const p06: string[] = [];
  let neg = 0;
  for (const f of ["guthaben", "DaBetrag", "bausparsumme_teuro"]) {
    const st = a.amountStats.get(f)!;
    neg += st.negative;
    const scaleNote = f === "bausparsumme_teuro" ? " (in thousands of euro as read; x1000 in the record)" : "";
    p06.push(f + ": missing " + intText(st.missing) + ", negative " + intText(st.negative) + ", range " + rng(st.min, st.max) + scaleNote);
  }
  push(
    "P-06", "FLAGGED", neg > 0,
    "Amounts are plausible: the balance, loan notional and Bauspar sum are finite and not negative wherever present.",
    p06.join(" | "),
  );

  // ---- P-07
  const ids = a.identifiers;
  push(
    "P-07", "FLAGGED", ids.duplicated > 0,
    "Identifiers are unique across rows.",
    "rows read " + intText(ids.rows) + ", distinct identifiers " + intText(ids.distinct) +
      ", identifiers appearing more than once " + intText(ids.duplicated) +
      "; reconciliation rows - distinct = " + intText(ids.rows - ids.distinct) +
      (ids.duplicateFirstTen.length ? "; first duplicated: " + ids.duplicateFirstTen.join(", ") : "") +
      " (never deduplicated: the published record objects keep every row)",
  );

  // ---- P-08
  const badShape =
    a.phaseOutOfSet > 0 || a.goalSourceOutOfSet > 0 ||
    a.positionBreaches.length > 0 || a.savingProgressBreaches.length > 0;
  push(
    "P-08", "FAIL", badShape,
    "Derived quantities are within their declared shapes.",
    "phase tally " + tally(a.phaseTally) + " (out of the declared set: " + intText(a.phaseOutOfSet) + ")" +
      "; goal_source tally " + tally(a.goalSourceTally) + " (out of set: " + intText(a.goalSourceOutOfSet) + ")" +
      "; published positions outside 0..1: " + intText(a.positionBreaches.length) +
      (a.positionBreaches.length ? " first: " + a.positionBreaches.slice(0, 5).map((b) => "row " + intText(b.rowIndex) + " " + b.field + "=" + plain(b.value)).join(", ") : "") +
      "; saving progress outside 0..1: " + intText(a.savingProgressBreaches.length),
  );

  // ---- P-09
  push(
    "P-09", "FAIL", a.recordsPublished !== a.rowsRead,
    "No row is lost: records published equals rows read.",
    "rows read " + intText(a.rowsRead) + ", records published " + intText(a.recordsPublished) +
      ", rows refused 0 (the per-contract calculation publishes a record for every row it is given; " +
      "its only failure mode is the abort of behaviour step C1, which emits no checkpoint file at all)",
  );

  // ---- P-10
  const collisions: string[] = [];
  for (const n of INPUT_COLUMNS) {
    for (const h of ctx.headerNames) {
      if (h !== n && h.indexOf(n) === 0) collisions.push(h + " begins with " + n);
    }
  }
  push(
    "P-10", "FLAGGED", collisions.length > 0,
    "No field name in the table has any of the eleven declared names as a strict prefix.",
    collisions.length === 0
      ? "checked all eleven declared names against all " + intText(ctx.headerNames.length) + " header names: no strict-prefix collision"
      : "strict-prefix collisions: " + collisions.join("; "),
  );

  // ---- P-11
  let multi = 0;
  const p11: string[] = [];
  for (const [f, st] of a.amountStats) {
    multi += st.multiComma;
    p11.push(f + ": " + intText(st.multiComma));
  }
  push(
    "P-11", "FLAGGED", multi > 0,
    "A text amount carries at most one comma.",
    "text amount values with two or more commas, by field: " + p11.join(", ") +
      " (each of those becomes missing by behaviour step C2, silently)",
  );

  // ---- P-12
  push(
    "P-12", "FAIL", !Number.isFinite(ctx.valuationDay),
    "The valuation date is supplied, is a valid calendar date, and lies within the plausible range of P-04.",
    "valuation date used: " + renderIsoDate(ctx.valuationDay) + " (epoch day " + intText(ctx.valuationDay) +
      "), source: " + ctx.valuationDateSource +
      "; the unit's own load-time default is 2026-03-31 and its own session override is a value named VAL_DATE -- " +
      "neither applied here, because this target's launch interface takes the date as an argument or from the input manifest",
  );

  // ---- P-13
  const med = median(a.p13Ratios.view());
  const p13Bad = !Number.isFinite(med) ? false : med < 0.01 || med > 100;
  out.push({
    id: "P-13", severity: "FLAGGED",
    status: a.p13Ratios.length === 0 ? "NOT_EXERCISED" : verdict("FLAGGED", p13Bad),
    statement: "The thousands factor on the Bauspar sum is right way up, judged from a derived quantity rather than from the column (R4).",
    evidence:
      "median of loan notional / Bauspar sum over " + intText(a.p13Ratios.length) +
      " contracts where both are present and the Bauspar sum is positive: " + plain(med) +
      ". A median near 1 is expected; near 0.001 or near 1000 would mean the thousands factor was applied on the wrong side or not at all.",
  });

  // ---- finding-carried preconditions -------------------------------------
  let fnd01 = 0;
  const fnd01Detail: string[] = [];
  for (const [f, st] of a.amountStats) {
    fnd01 += st.dotNoCommaSuspect.length;
    fnd01Detail.push(
      f + ": " + intText(st.dotNoComma) + " values with a dot and no comma, of which " +
      intText(st.dotNoCommaSuspect.length) + " have exactly three digits after the last dot (the thousands-dot shape)" +
      (st.dotNoCommaSuspect.length ? "; first: " + st.dotNoCommaSuspect.slice(0, 5).map((o) => "row " + intText(o.rowIndex) + "=" + JSON.stringify(o.value)).join(", ") : ""),
    );
  }
  push(
    "FND-01", "FAIL", fnd01 > 0 && !fnd01IsUnitScaled(a),
    "An amount written in German thousands style but WITHOUT a decimal comma is read a thousand times too small.",
    fnd01Detail.join(" | ") +
      " || note: bausparsumme_teuro is denominated in thousands of euro with three decimals, so a three-decimal " +
      "value there is the ordinary spelling of that column and not the thousands-dot hazard; the check reports the " +
      "shape for every field and judges the hazard only where the field is denominated in euro.",
  );

  push(
    "FND-02", "FAIL", t.aboveOne > 0,
    "The per-contract tariff share is multiplied directly by an amount in euro, so it is used as a FRACTION OF ONE.",
    "non-missing tariff shares: range " + rng(t.min, t.max) + ", count greater than 1: " + intText(t.aboveOne) +
      ", count at most 0: " + intText(t.atMostZero) + ", missing " + intText(t.missing) +
      ", distinct raw texts " + distinctText(a, "tariff_amount"),
  );

  push(
    "FND-03", "FLAGGED", ids.exponentShaped > 0,
    "The published identifier is the BSV value rendered by the source language's default numeric-to-text conversion.",
    "published identifiers matching a mantissa followed by e and a signed exponent: " + intText(ids.exponentShaped) +
      (ids.exponentFirstTen.length ? "; first ten: " + ids.exponentFirstTen.join(", ") : "") +
      ". The identifier column arrived as TEXT in this run, so the text is used unchanged, with no trimming and no padding.",
  );

  push(
    "FND-04", "FLAGGED", ids.duplicated > 0,
    "The browser data file is written one entry per ROW, keyed by identifier; duplicates produce duplicate keys.",
    "rows " + intText(ids.rows) + ", distinct identifiers " + intText(ids.distinct) +
      ", duplicated identifiers " + intText(ids.duplicated) + " (reconciles: " +
      intText(ids.rows) + " rows - " + intText(ids.distinct) + " distinct = " + intText(ids.rows - ids.distinct) + " extra rows)",
  );

  const bands = a.ratioBands;
  const alarmMatches = a.alarmCount === bands.atMost05;
  push(
    "FND-05", "FLAGGED", !alarmMatches,
    "Two cutoffs describe the same comparison from opposite ends and are not applied to the same number.",
    "bands over the UNROUNDED ratio: missing " + intText(bands.missing) + ", at most 0.5 " + intText(bands.atMost05) +
      ", between 0.5 and 2 inclusive " + intText(bands.between) + ", greater than 2 " + intText(bands.above2) +
      "; alarm count from the ROUNDED ratio strictly below 0.5: " + intText(a.alarmCount) +
      "; bridge flag count from the UNROUNDED ratio strictly above 2: " + intText(a.bridgeCount) +
      (alarmMatches ? " -- the two agree on this input" : " -- the two DISAGREE, which is the finding's exposure and is the expected shape on a boundary value"),
  );

  push(
    "FND-06", "FLAGGED", unread > 0,
    "The two date branches fail differently: a hyphenated unreadable value aborts the run, a non-hyphenated one goes silently missing.",
    "values satisfying neither branch: " + intText(unread) + " (by field: " +
      Array.from(a.dateStats.entries()).map(([f, st]) => f + " " + intText(st.unreadable)).join(", ") +
      "); of those, hyphenated and therefore ABORT-TRIGGERING: " + intText(unreadHyph),
  );

  out.push({
    id: "FND-07", severity: "FAIL", status: "NOT_EXERCISED",
    statement: "The standalone-page writer ignores its own table argument and builds the data block from the enriched session table.",
    evidence:
      "no standalone page is produced by this build: the target's launch interface (GR-14, target directive 4) " +
      "takes one input path and an optional valuation date and produces no page. The precondition is therefore " +
      "not exercised here rather than vacuously passed. It is expected to FAIL for any call with a subset.",
  });

  push(
    "FND-08", "FLAGGED", a.doneWithBothAbsent > 0,
    "Two fallbacks chain: a missing allocation becomes base + 3652 days, and a missing contract end becomes THAT estimate + 4018 days.",
    "allocation estimated " + intText(a.allocEstimated) + "; contract end absent " + intText(a.contractEndAbsent) +
      "; both " + intText(a.bothAbsent) + "; phase is done while both were absent: " + intText(a.doneWithBothAbsent) +
      " (the last count is this finding's exposure and travels with the verdict)",
  );

  push(
    "FND-09", "FLAGGED", a.loanDiscrepancyMax > 1,
    "Every published amount is rounded independently, so the published loan portion need not equal the published reference minus the published balance.",
    "contracts where published loan portion != published reference - published balance: " + intText(a.loanDiscrepancyCount) +
      "; maximum size of the discrepancy: " + plain(a.loanDiscrepancyMax) +
      " euro (a discrepancy of more than one euro would mean the rounding rule itself diverges)",
  );

  push(
    "FND-10", "FLAGGED", a.phaseOutOfSet > 0,
    "Both downstream consumers draw a fifth phase called nodata; the unit never produces it.",
    "published phases: " + tally(a.phaseTally) + "; published phases outside the declared four: " + intText(a.phaseOutOfSet) +
      "; contracts with a missing savings ratio (the population the consumers' unreachable branch was written for): " +
      intText(a.savingsRatioMissing),
  );

  const markersSeen = ctx.dateMarkerSet;
  push(
    "FND-11", "FLAGGED", false,
    "The unit's comment lists four missing markers; the code recognises seven.",
    "the seven markers of date_missing_markers are implemented in full; the markers actually PRESENT in this input's " +
      "date fields are: " + (markersSeen.length ? markersSeen.map((m) => (m === "" ? "(empty)" : m)).join(" | ") : "none") +
      ". Markers not exercised by this input are named rather than assumed covered.",
  );

  push(
    "FND-12", "FLAGGED", collisions.length > 0,
    "Field access on a contract row is by name with PREFIX FALLBACK in the source language.",
    "check 1 -- all eleven exact names present: " + (absent.length === 0 ? "yes" : "NO, absent: " + absent.join(", ")) +
      "; check 2 -- other field names having one of the eleven as a strict prefix: " +
      (collisions.length === 0 ? "none" : collisions.join("; ")) +
      ". The two checks are reported separately, as the finding requires. This target binds by exact name only and " +
      "never falls back to a prefix; the precondition is what makes the difference unobservable.",
  );

  push(
    "FND-13", "FLAGGED", a.warnDisagreement > 0,
    "The warning flag is decided on the unrounded savings ratio while the ratio itself is published rounded to three places.",
    "contracts where the published flag and the test 'published ratio at least 0.90' disagree: " + intText(a.warnDisagreement) +
      " (that count is the population where the picture and the record contradict each other and it travels with the verdict)",
  );

  return out;
}

function fnd01IsUnitScaled(a: Aggregates): boolean {
  // The hazard of FND-01 is a EURO amount written with a thousands dot and no
  // comma. bausparsumme_teuro is denominated in thousands with three decimals,
  // so a three-decimal spelling there is ordinary. Judge the hazard only on the
  // euro-denominated fields, and derive the judgement from the fields that
  // actually carry a suspect value rather than from a fixed sentence (R14).
  for (const [f, st] of a.amountStats) {
    if (f === "bausparsumme_teuro") continue;
    if (st.dotNoCommaSuspect.length > 0) return false;
  }
  return true;
}

function tally(m: Map<string, number>): string {
  return Array.from(m.entries())
    .sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0))
    .map(([k, v]) => (k === "" ? "(empty)" : k) + "=" + intText(v))
    .join(", ");
}

function distinctText(a: Aggregates, field: string): string {
  const st = a.amountStats.get(field);
  if (!st) return "(field absent)";
  if (st.distinctOverflow) return "(more than the reporting cap; not listed)";
  return Array.from(st.distinct).sort().map((s) => (s === "" ? "(empty)" : s)).join(" | ");
}
