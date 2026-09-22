// src/table.ts
//
// The table driver: two streaming passes over the contract table.
//
// PASS A applies the harness coercions declared in the input manifest. The
// source-side harness converts a whole column to a date type BEFORE the unit
// sees any row, and the source language's conversion infers its format from the
// FIRST NON-MISSING element of that column and then applies it to the rest.
// Controller directive 01 makes the consequence binding: in a coerced column,
// only a bad value in the first non-missing position aborts; anywhere else it
// goes quietly missing. Doing this in a separate pass is not an optimisation --
// it is what puts the abort BEFORE row 1 completes, where the source puts it.
//
// PASS B computes the contracts. In a column the unit parses itself, every
// hyphenated unparseable value aborts, at whatever row it sits, because the unit
// hands the reader one value at a time and that value is always the first
// element of its own vector.
//
// Neither pass reads the file whole (GR-09).

import { parseCsv } from "./csv.js";
import {
  DateParseAbort, detectStandardFormat, isDateMissingMarker, parseWithStandardFormat,
  parseEightDigits,
} from "./dates.js";
import { readAmountText } from "./numbers.js";
import {
  computeContract, mapExport, RECORD_FIELDS, EXPORT_FIELDS,
  type RawRow, type EngineConfig, type ContractRecord, type ExportValue,
} from "./engine.js";
import { renderEntry } from "./script.js";
import { makeStore, pushBool, pushNum, pushStr, F64Vec, type ObjectStore } from "./store.js";
import { Journal, Progress } from "./logging.js";
import { intText } from "./canonical.js";

export const DATE_FIELDS = [
  "abschlussdatum", "einloesungsdatum", "erstmalige_zuteilungsanwartschaft",
  "Tilgungsbeginn", "Vertragsende",
] as const;
export const AMOUNT_FIELDS = ["DaBetrag", "bausparsumme_teuro", "guthaben", "tariff_amount"] as const;

export interface DateFieldStats {
  field: string;
  coerced: boolean;
  marker: number;
  hyphenValid: number;
  eightDigitValid: number;
  unreadable: number;
  unreadableHyphenated: number;
  offenders: Array<{ rowIndex: number; value: string }>;
  minDay: number;
  maxDay: number;
  parsedCount: number;
  outOfPlausibleRange: number;
}

export interface AmountFieldStats {
  field: string;
  missing: number;
  negative: number;
  min: number;
  max: number;
  multiComma: number;
  /** FND-01: dot present, no comma -- the thousands-dot hazard */
  dotNoComma: number;
  dotNoCommaSuspect: Array<{ rowIndex: number; value: string }>;
  /** the text "0", which behaviour step C2 reads as a ZERO and not as a missing value */
  zeroText: number;
  emptyText: number;
  distinct: Set<string>;
  distinctOverflow: boolean;
}

export interface Aggregates {
  rowsRead: number;
  recordsPublished: number;
  dateStats: Map<string, DateFieldStats>;
  amountStats: Map<string, AmountFieldStats>;
  identifiers: {
    rows: number;
    distinct: number;
    duplicated: number;
    exponentShaped: number;
    exponentFirstTen: string[];
    duplicateFirstTen: string[];
  };
  phaseTally: Map<string, number>;
  goalSourceTally: Map<string, number>;
  contractTypeTally: Map<string, number>;
  positionBreaches: Array<{ rowIndex: number; field: string; value: number }>;
  savingProgressBreaches: Array<{ rowIndex: number; value: number }>;
  /** FND-05 bands over the UNROUNDED ratio, plus the alarm count from the ROUNDED one */
  ratioBands: { missing: number; atMost05: number; between: number; above2: number };
  alarmCount: number;
  bridgeCount: number;
  /** FND-08 */
  allocEstimated: number;
  contractEndAbsent: number;
  bothAbsent: number;
  doneWithBothAbsent: number;
  /** FND-09 */
  loanDiscrepancyCount: number;
  loanDiscrepancyMax: number;
  /** FND-10 */
  savingsRatioMissing: number;
  phaseOutOfSet: number;
  goalSourceOutOfSet: number;
  /** FND-13 */
  warnDisagreement: number;
  /** P-13 */
  p13Ratios: F64Vec;
  tariff: { min: number; max: number; atMostZero: number; aboveOne: number; missing: number };
}

function newDateStats(field: string, coerced: boolean): DateFieldStats {
  return {
    field, coerced, marker: 0, hyphenValid: 0, eightDigitValid: 0, unreadable: 0,
    unreadableHyphenated: 0, offenders: [], minDay: NaN, maxDay: NaN, parsedCount: 0,
    outOfPlausibleRange: 0,
  };
}
function newAmountStats(field: string): AmountFieldStats {
  return {
    field, missing: 0, negative: 0, min: Infinity, max: -Infinity, multiComma: 0,
    dotNoComma: 0, dotNoCommaSuspect: [], zeroText: 0, emptyText: 0,
    distinct: new Set<string>(), distinctOverflow: false,
  };
}

export interface CoercionOutcome {
  column: string;
  format: "%Y-%m-%d" | "%Y/%m/%d" | null;
  firstNonMissingRow: number;
  firstNonMissingValue: string | null;
}

/**
 * PASS A. Determine, for each column the manifest declares as coerced to a date
 * type, the format the source language's conversion would infer, and raise the
 * abort if that first non-missing value is hyphenated and unreadable.
 */
export function coerceColumns(
  inputPath: string,
  delimiter: string,
  headerIndex: number,
  fieldIndex: Map<string, number>,
  coercedColumns: string[],
  journal: Journal,
): Map<string, CoercionOutcome> {
  const state = new Map<string, CoercionOutcome>();
  for (const c of coercedColumns) {
    state.set(c, { column: c, format: null, firstNonMissingRow: -1, firstNonMissingValue: null });
  }
  let pending = coercedColumns.filter((c) => fieldIndex.has(c)).length;
  for (const c of coercedColumns) {
    if (!fieldIndex.has(c)) {
      journal.note({
        kind: "declined", where: "harness coercion", what: "declared coerced column '" + c + "'",
        why: "the table does not carry a field with that name, so no coercion was applied to it",
        rowIndex: null, column: c,
      });
    }
  }
  if (pending === 0) return state;

  let abort: DateParseAbort | null = null;
  parseCsv(inputPath, { delimiter, quote: '"' }, (fields, recordIndex) => {
    if (recordIndex <= headerIndex) return true;
    const rowIndex = recordIndex - headerIndex;
    for (const c of coercedColumns) {
      const st = state.get(c)!;
      if (st.firstNonMissingRow > 0) continue;
      const ix = fieldIndex.get(c);
      if (ix === undefined) continue;
      const raw = fields[ix] ?? "";
      const t = raw.trim();
      if (isDateMissingMarker(t)) continue;
      st.firstNonMissingRow = rowIndex;
      st.firstNonMissingValue = raw;
      st.format = detectStandardFormat(t);
      pending -= 1;
      if (st.format === null) {
        if (t.indexOf("-") >= 0) {
          // Controller directive 01: hyphenated, not accepted by the standard
          // unambiguous parse, and the first non-missing element of the vector
          // the conversion is applied to. This aborts before any row completes.
          abort = new DateParseAbort(raw, c, rowIndex);
          return false;
        }
        journal.note({
          kind: "fallback", where: "harness coercion",
          what: "column '" + c + "' first non-missing value " + JSON.stringify(raw),
          why: "not in a standard unambiguous format and carries no hyphen, so the whole column coerces to missing (no abort -- controller directive 01)",
          rowIndex, column: c,
        });
      }
    }
    return pending > 0;
  });
  if (abort !== null) throw abort;
  return state;
}

export interface RunOutput {
  book: ObjectStore;
  exportRows: ObjectStore;
  entries: string[];
  aggregates: Aggregates;
  coercions: Map<string, CoercionOutcome>;
}

const PLAUSIBLE_MIN_DAY = -7305;   // 1950-01-01
const PLAUSIBLE_MAX_DAY = 47482;   // 2100-01-01
const DISTINCT_CAP = 64;

/** PASS B. Compute every row and fill both published objects plus the document entries. */
export function runTable(
  inputPath: string,
  delimiter: string,
  headerIndex: number,
  fieldIndex: Map<string, number>,
  coercions: Map<string, CoercionOutcome>,
  valuationDay: number,
  cfg: EngineConfig,
  journal: Journal,
  expectedRows: number | null,
): RunOutput {
  const book = makeStore("customer_book", [
    ["row_index", "num"], ["id", "str"], ["phase", "str"], ["savings_ratio", "num"],
    ["saving_goal", "num"], ["contract_type", "str"], ["goal_fraction", "num"],
    ["goal_source", "str"], ["saving_reference", "num"], ["balance", "num"],
    ["bauspar_sum", "num"], ["loan_notional", "num"], ["bauspar_loan", "num"],
    ["loan_to_bauspar_ratio", "num"], ["is_bridge_loan", "bool"], ["allocation_estimated", "bool"],
    ["allocation_in_past", "bool"], ["repayment_active", "bool"], ["saving_after_allocation", "bool"],
    ["warn_loan_pointless", "bool"], ["contract_start_date", "date"], ["first_payment_date", "date"],
    ["allocation_date", "date"], ["loan_start_date", "date"], ["contract_end_date", "date"],
    ["year_contract", "str"], ["year_first_payment", "str"], ["year_allocation", "str"],
    ["year_loan_start", "str"], ["x_contract", "num"], ["x_first_payment", "num"],
    ["x_allocation", "num"], ["x_loan_start", "num"], ["x_now", "num"],
  ]);
  const exportRows = makeStore("customer_export_rows", [
    ["row_index", "num"], ["id", "str"], ["phase", "str"], ["warn", "num"], ["sr", "num"],
    ["xc", "num"], ["xf", "num"], ["xa", "num"], ["xl", "num"], ["xn", "num"],
    ["lab_contract", "str"], ["lab_first", "str"], ["lab_alloc", "str"], ["lab_loan", "str"],
    ["guthaben", "num"], ["bausparsumme", "num"], ["save_target", "num"], ["loan_amount", "num"],
    ["dabetrag", "num"], ["alloc_est", "num"], ["da_bsum_ratio", "num"], ["bridge", "num"],
    ["goal_frac", "num"], ["contract_type", "str"], ["goal_source", "str"], ["special", "num"],
  ]);

  const agg: Aggregates = {
    rowsRead: 0, recordsPublished: 0,
    dateStats: new Map(), amountStats: new Map(),
    identifiers: { rows: 0, distinct: 0, duplicated: 0, exponentShaped: 0, exponentFirstTen: [], duplicateFirstTen: [] },
    phaseTally: new Map(), goalSourceTally: new Map(), contractTypeTally: new Map(),
    positionBreaches: [], savingProgressBreaches: [],
    ratioBands: { missing: 0, atMost05: 0, between: 0, above2: 0 },
    alarmCount: 0, bridgeCount: 0,
    allocEstimated: 0, contractEndAbsent: 0, bothAbsent: 0, doneWithBothAbsent: 0,
    loanDiscrepancyCount: 0, loanDiscrepancyMax: 0,
    savingsRatioMissing: 0, phaseOutOfSet: 0, goalSourceOutOfSet: 0,
    warnDisagreement: 0,
    p13Ratios: new F64Vec(),
    tariff: { min: Infinity, max: -Infinity, atMostZero: 0, aboveOne: 0, missing: 0 },
  };
  for (const f of DATE_FIELDS) agg.dateStats.set(f, newDateStats(f, coercions.has(f)));
  for (const f of AMOUNT_FIELDS) agg.amountStats.set(f, newAmountStats(f));

  const idSeen = new Map<string, number>();
  const entries: string[] = [];
  const EXP_RE = /^[+-]?\d*\.?\d+[eE][+-]?\d+$/;
  const progress = new Progress("compute contracts", expectedRows);

  const dateInput = (col: string, raw: string | null) => {
    const co = coercions.get(col);
    if (co !== undefined) {
      if (raw === null) return { coerced: true as const, day: NaN, column: col };
      const t = raw.trim();
      if (isDateMissingMarker(t) || co.format === null) return { coerced: true as const, day: NaN, column: col };
      const v = parseWithStandardFormat(t, co.format);
      return { coerced: true as const, day: v === null ? NaN : v, column: col };
    }
    return { coerced: false as const, text: raw, column: col };
  };

  const get = (fields: string[], name: string): string | null => {
    const ix = fieldIndex.get(name);
    if (ix === undefined) return null;
    return fields[ix] ?? "";
  };

  parseCsv(inputPath, { delimiter, quote: '"' }, (fields, recordIndex) => {
    if (recordIndex <= headerIndex) return true;
    const rowIndex = recordIndex - headerIndex;
    agg.rowsRead = rowIndex;

    // --- raw-text classification for the precondition reports (R14: the
    //     explanation is worked out from the value at the point of the finding)
    for (const f of DATE_FIELDS) {
      const st = agg.dateStats.get(f)!;
      const raw = get(fields, f);
      if (raw === null) continue;
      const t = raw.trim();
      if (isDateMissingMarker(t)) { st.marker += 1; continue; }
      if (t.indexOf("-") >= 0) {
        const v = detectStandardFormat(t) !== null;
        if (v) st.hyphenValid += 1;
        else {
          st.unreadable += 1; st.unreadableHyphenated += 1;
          if (st.offenders.length < 10) st.offenders.push({ rowIndex, value: raw });
        }
      } else {
        const v = parseEightDigits(t);
        if (v !== null) st.eightDigitValid += 1;
        else {
          st.unreadable += 1;
          if (st.offenders.length < 10) st.offenders.push({ rowIndex, value: raw });
        }
      }
    }
    for (const f of AMOUNT_FIELDS) {
      const st = agg.amountStats.get(f)!;
      const raw = get(fields, f);
      if (raw === null) continue;
      const t = raw.trim();
      if (t === "0") st.zeroText += 1;
      if (t === "") st.emptyText += 1;
      if (t.split(",").length - 1 >= 2) st.multiComma += 1;
      if (t.indexOf(",") < 0 && t.indexOf(".") >= 0) {
        st.dotNoComma += 1;
        const afterLastDot = t.length - t.lastIndexOf(".") - 1;
        if (afterLastDot === 3 && st.dotNoCommaSuspect.length < 10) {
          st.dotNoCommaSuspect.push({ rowIndex, value: raw });
        }
      }
      if (!st.distinctOverflow) {
        st.distinct.add(t);
        if (st.distinct.size > DISTINCT_CAP) st.distinctOverflow = true;
      }
      const out = readAmountText(t);
      if (Number.isNaN(out.value)) {
        st.missing += 1;
        if (out.how === "unparsed_missing") {
          journal.note({
            kind: "fallback", where: "number reader (behaviour step C2)",
            what: "value " + JSON.stringify(raw) + " in field " + f,
            why: "does not read as a number after the comma/dot transform, so the amount is missing -- the source does this silently",
            rowIndex, column: f,
          });
        }
      } else {
        if (out.value < 0) st.negative += 1;
        if (out.value < st.min) st.min = out.value;
        if (out.value > st.max) st.max = out.value;
      }
    }

    // --- the unit itself
    const tariffRaw = get(fields, "tariff_amount");
    const ctRaw = get(fields, "contract_type");
    const row: RawRow = {
      bsv: get(fields, "BSV"),
      abschlussdatum: dateInput("abschlussdatum", get(fields, "abschlussdatum")),
      einloesungsdatum: dateInput("einloesungsdatum", get(fields, "einloesungsdatum")),
      erstmalige: dateInput("erstmalige_zuteilungsanwartschaft", get(fields, "erstmalige_zuteilungsanwartschaft")),
      tilgungsbeginn: dateInput("Tilgungsbeginn", get(fields, "Tilgungsbeginn")),
      vertragsende: dateInput("Vertragsende", get(fields, "Vertragsende")),
      daBetrag: get(fields, "DaBetrag"),
      bausparsummeTeuro: get(fields, "bausparsumme_teuro"),
      guthaben: get(fields, "guthaben"),
      tariffAmount: tariffRaw,
      contractType: ctRaw,
      contractTypePresent: fieldIndex.has("contract_type"),
      tariffPresent: fieldIndex.has("tariff_amount"),
    };
    const rec = computeContract(row, valuationDay, cfg, rowIndex);
    agg.recordsPublished += 1;

    writeBookRow(book, rowIndex, rec);
    const ev = mapExport(rec);
    writeExportRow(exportRows, rowIndex, ev);
    entries.push(renderEntry(rec.id, ev));

    accumulate(agg, rowIndex, rec, ev, row, idSeen, EXP_RE, valuationDay);

    if (rowIndex % 1000 === 0) progress.tick(rowIndex);
    return true;
  });
  progress.done(agg.rowsRead);

  agg.identifiers.rows = agg.rowsRead;
  agg.identifiers.distinct = idSeen.size;
  let dup = 0;
  for (const [k, v] of idSeen) {
    if (v > 1) {
      dup += 1;
      if (agg.identifiers.duplicateFirstTen.length < 10) agg.identifiers.duplicateFirstTen.push(k);
    }
  }
  agg.identifiers.duplicated = dup;

  journal.note({
    kind: "info", where: "parse reconciliation (GR-08)",
    what: "rows read " + intText(agg.rowsRead) + ", records published " + intText(agg.recordsPublished) +
      ", rows refused 0",
    why: "the per-contract calculation is total: it publishes a record for every row it is given",
    rowIndex: null, column: null,
  });

  return { book, exportRows, entries, aggregates: agg, coercions };
}

function writeBookRow(s: ObjectStore, rowIndex: number, r: ContractRecord): void {
  let i = 0;
  pushNum(s, i++, rowIndex);
  pushStr(s, i++, r.id);
  pushStr(s, i++, r.phase);
  pushNum(s, i++, r.savings_ratio);
  pushNum(s, i++, r.saving_goal);
  pushStr(s, i++, r.contract_type);
  pushNum(s, i++, r.goal_fraction);
  pushStr(s, i++, r.goal_source);
  pushNum(s, i++, r.saving_reference);
  pushNum(s, i++, r.balance);
  pushNum(s, i++, r.bauspar_sum);
  pushNum(s, i++, r.loan_notional);
  pushNum(s, i++, r.bauspar_loan);
  pushNum(s, i++, r.loan_to_bauspar_ratio);
  pushBool(s, i++, r.is_bridge_loan);
  pushBool(s, i++, r.allocation_estimated);
  pushBool(s, i++, r.allocation_in_past);
  pushBool(s, i++, r.repayment_active);
  pushBool(s, i++, r.saving_after_allocation);
  pushBool(s, i++, r.warn_loan_pointless);
  pushNum(s, i++, r.contract_start_date);
  pushNum(s, i++, r.first_payment_date);
  pushNum(s, i++, r.allocation_date);
  pushNum(s, i++, r.loan_start_date);
  pushNum(s, i++, r.contract_end_date);
  pushStr(s, i++, r.year_contract);
  pushStr(s, i++, r.year_first_payment);
  pushStr(s, i++, r.year_allocation);
  pushStr(s, i++, r.year_loan_start);
  pushNum(s, i++, r.x_contract);
  pushNum(s, i++, r.x_first_payment);
  pushNum(s, i++, r.x_allocation);
  pushNum(s, i++, r.x_loan_start);
  pushNum(s, i++, r.x_now);
  if (i !== RECORD_FIELDS.length + 1) throw new Error("customer_book column count drifted from record_field_catalogue");
}

function writeExportRow(s: ObjectStore, rowIndex: number, ev: ExportValue[]): void {
  pushNum(s, 0, rowIndex);
  for (let k = 0; k < EXPORT_FIELDS.length; k++) {
    const col = s.columns[k + 1]!;
    const v = ev[k]!;
    if (col.kind === "str") pushStr(s, k + 1, v === null ? null : (v as string));
    else pushNum(s, k + 1, v === null ? NaN : (v as number));
  }
}

function bump(m: Map<string, number>, k: string): void {
  m.set(k, (m.get(k) ?? 0) + 1);
}

function accumulate(
  agg: Aggregates, rowIndex: number, r: ContractRecord, ev: ExportValue[],
  raw: RawRow, idSeen: Map<string, number>, EXP_RE: RegExp, valuationDay: number,
): void {
  void raw;
  void valuationDay;
  const id = r.id ?? "";
  idSeen.set(id, (idSeen.get(id) ?? 0) + 1);
  if (EXP_RE.test(id)) {
    agg.identifiers.exponentShaped += 1;
    if (agg.identifiers.exponentFirstTen.length < 10) agg.identifiers.exponentFirstTen.push(id);
  }
  bump(agg.phaseTally, r.phase);
  bump(agg.goalSourceTally, r.goal_source);
  bump(agg.contractTypeTally, r.contract_type === null ? "<absent>" : r.contract_type);

  for (const [name, v] of [
    ["x_contract", r.x_contract], ["x_first_payment", r.x_first_payment],
    ["x_allocation", r.x_allocation], ["x_loan_start", r.x_loan_start], ["x_now", r.x_now],
  ] as Array<[string, number]>) {
    if (!Number.isNaN(v) && (v < 0 || v > 1) && agg.positionBreaches.length < 20) {
      agg.positionBreaches.push({ rowIndex, field: name, value: v });
    }
  }
  const sp = r.unrounded.saving_progress;
  if ((sp < 0 || sp > 1) && agg.savingProgressBreaches.length < 20) {
    agg.savingProgressBreaches.push({ rowIndex, value: sp });
  }

  const ur = r.unrounded.loan_to_bauspar_ratio;
  if (!Number.isFinite(ur)) agg.ratioBands.missing += 1;
  else if (ur <= 0.5) agg.ratioBands.atMost05 += 1;
  else if (ur <= 2) agg.ratioBands.between += 1;
  else agg.ratioBands.above2 += 1;
  if (ev[24] === 1) agg.alarmCount += 1;
  if (r.is_bridge_loan) agg.bridgeCount += 1;

  if (r.allocation_estimated) agg.allocEstimated += 1;
  const endAbsent = r.unrounded.contract_end_estimated;
  if (endAbsent) agg.contractEndAbsent += 1;
  if (r.allocation_estimated && endAbsent) {
    agg.bothAbsent += 1;
    if (r.phase === "done") agg.doneWithBothAbsent += 1;
  }

  if (Number.isFinite(r.saving_reference) && Number.isFinite(r.balance) && Number.isFinite(r.bauspar_loan)) {
    const d = Math.abs(r.bauspar_loan - (r.saving_reference - r.balance));
    if (d > 0) {
      agg.loanDiscrepancyCount += 1;
      if (d > agg.loanDiscrepancyMax) agg.loanDiscrepancyMax = d;
    }
  }

  if (!Number.isFinite(r.unrounded.savings_ratio)) agg.savingsRatioMissing += 1;
  if (["done", "loan", "oversave", "save"].indexOf(r.phase) < 0) agg.phaseOutOfSet += 1;
  if (["tariff", "fallback_no_tariff"].indexOf(r.goal_source) < 0) agg.goalSourceOutOfSet += 1;

  const publishedAtLeast = Number.isFinite(r.savings_ratio) && r.savings_ratio >= 0.9;
  if (publishedAtLeast !== r.warn_loan_pointless) agg.warnDisagreement += 1;

  if (Number.isFinite(r.unrounded.loan_to_bauspar_ratio)) agg.p13Ratios.push(r.unrounded.loan_to_bauspar_ratio);

  const tv = r.unrounded.tariff_value;
  if (!Number.isFinite(tv)) agg.tariff.missing += 1;
  else {
    if (tv < agg.tariff.min) agg.tariff.min = tv;
    if (tv > agg.tariff.max) agg.tariff.max = tv;
    if (tv <= 0) agg.tariff.atMostZero += 1;
    if (tv > 1) agg.tariff.aboveOne += 1;
  }

  // P-04: the minimum and maximum of each of the five PARSED date fields, taken
  // from the values the unit actually read, before any fallback substituted one.
  const parsed: Array<[string, number]> = [
    ["abschlussdatum", r.unrounded.parsed_start],
    ["einloesungsdatum", r.unrounded.parsed_first_payment],
    ["erstmalige_zuteilungsanwartschaft", r.unrounded.parsed_allocation],
    ["Tilgungsbeginn", r.unrounded.parsed_repayment],
    ["Vertragsende", r.unrounded.parsed_end],
  ];
  for (const [f, day] of parsed) {
    if (Number.isNaN(day)) continue;
    const st = agg.dateStats.get(f)!;
    st.parsedCount += 1;
    if (Number.isNaN(st.minDay) || day < st.minDay) st.minDay = day;
    if (Number.isNaN(st.maxDay) || day > st.maxDay) st.maxDay = day;
    if (day < PLAUSIBLE_MIN_DAY || day > PLAUSIBLE_MAX_DAY) st.outOfPlausibleRange += 1;
  }
}

