// src/engine.ts
//
// Neutral spec unit U01, behaviour steps C0 through C21 and C25.
// The per-contract calculation, the whole-book shape, and the export mapping.
//
// FINDINGS POLICY: FAITHFUL ONLY (target directive 13). Where the spec records a
// defect as the source's behaviour it is implemented here as the source does it.
// There is no switch, no corrected variant and no delta report. Each such place
// is marked with its finding id so that a reader can tell a reproduced defect
// from an accident.

import { readDateText } from "./dates.js";
import { yearLabel } from "./dates.js";
import { readAmountText } from "./numbers.js";
import { roundRecord, clamp01 } from "./round.js";

// --- constants of the unit (neutral spec `constants`) -----------------------

export const RECORD_FIELDS: readonly string[] = [
  "id", "phase", "savings_ratio", "saving_goal", "contract_type", "goal_fraction",
  "goal_source", "saving_reference", "balance", "bauspar_sum", "loan_notional",
  "bauspar_loan", "loan_to_bauspar_ratio", "is_bridge_loan", "allocation_estimated",
  "allocation_in_past", "repayment_active", "saving_after_allocation",
  "warn_loan_pointless", "contract_start_date", "first_payment_date",
  "allocation_date", "loan_start_date", "contract_end_date", "year_contract",
  "year_first_payment", "year_allocation", "year_loan_start", "x_contract",
  "x_first_payment", "x_allocation", "x_loan_start", "x_now",
];

export const EXPORT_FIELDS: readonly string[] = [
  "id", "phase", "warn", "sr", "xc", "xf", "xa", "xl", "xn", "lab_contract",
  "lab_first", "lab_alloc", "lab_loan", "guthaben", "bausparsumme", "save_target",
  "loan_amount", "dabetrag", "alloc_est", "da_bsum_ratio", "bridge", "goal_frac",
  "contract_type", "goal_source", "special",
];

export const INPUT_COLUMNS: readonly string[] = [
  "BSV", "DaBetrag", "Tilgungsbeginn", "Vertragsende", "abschlussdatum",
  "bausparsumme_teuro", "contract_type", "einloesungsdatum",
  "erstmalige_zuteilungsanwartschaft", "guthaben", "tariff_amount",
];

export const PHASE_VALUES: readonly string[] = ["done", "loan", "oversave", "save"];
export const GOAL_SOURCE_VALUES: readonly string[] = ["tariff", "fallback_no_tariff"];

export const ROUNDING_PLACES: Readonly<Record<string, number>> = {
  savings_ratio: 3, saving_goal: 0, goal_fraction: 4, saving_reference: 0,
  balance: 0, bauspar_sum: 0, loan_notional: 0, bauspar_loan: 0,
  loan_to_bauspar_ratio: 3, x_contract: 4, x_first_payment: 4, x_allocation: 4,
  x_loan_start: 4, x_now: 4,
};

/** The seven configuration values of behaviour step C0, at the unit's defaults. */
export interface EngineConfig {
  preferTariffShare: boolean;          // prefer_tariff_share            = true
  savingGoalFractionDefault: number;   // saving_goal_fraction_default   = 0.40
  bridgeRatioCutoff: number;           // bridge_ratio_cutoff            = 2
  warnBalanceFraction: number;         // warn_balance_fraction          = 0.90
  allocationFallbackDays: number;      // allocation_fallback_days       = 3652
  contractEndFallbackDays: number;     // contract_end_fallback_days     = 4018
  fallbackOriginDays: number;          // fallback_origin_days           = 2557
}

export const DEFAULT_CONFIG: EngineConfig = {
  preferTariffShare: true,
  savingGoalFractionDefault: 0.4,
  bridgeRatioCutoff: 2,
  warnBalanceFraction: 0.9,
  allocationFallbackDays: 3652,
  contractEndFallbackDays: 4018,
  fallbackOriginDays: 2557,
};

export const BAUSPAR_SUM_UNIT_FACTOR = 1000;
export const SPECIAL_ALARM_RATIO_CUTOFF = 0.5;
export const AXIS_CONTRACT = 0.02;
export const AXIS_FIRST_PAYMENT = 0.06;
export const AXIS_ALLOCATION = 0.4;
export const OVERSAVE_BUMP = 0.06;
export const OVERSAVE_CAP = 0.46;
export const FORTSETZER_WEDGE = 0.18;
export const LOAN_REGION_WIDTH = 0.6;
export const SAVING_REGION_WIDTH = 0.34;

// --- row input --------------------------------------------------------------

/**
 * A date field as it reaches the unit. `coerced` means the harness converted the
 * whole column to a date type before the unit saw it (behaviour step C1, first
 * clause); otherwise the unit parses the text itself and the abort of FND-06 is
 * reachable at every row of that column.
 */
export type DateInput =
  | { coerced: true; day: number; column: string }
  | { coerced: false; text: string | null; column: string };

export interface RawRow {
  bsv: string | null;
  abschlussdatum: DateInput;
  einloesungsdatum: DateInput;
  erstmalige: DateInput;
  tilgungsbeginn: DateInput;
  vertragsende: DateInput;
  daBetrag: string | null;
  bausparsummeTeuro: string | null;
  guthaben: string | null;
  tariffAmount: string | null;
  /** null means the field is ABSENT from the row, which C9 distinguishes from an empty text */
  contractType: string | null;
  contractTypePresent: boolean;
  tariffPresent: boolean;
}

export interface ContractRecord {
  id: string | null;
  phase: string;
  savings_ratio: number;
  saving_goal: number;
  contract_type: string | null;
  goal_fraction: number;
  goal_source: string;
  saving_reference: number;
  balance: number;
  bauspar_sum: number;
  loan_notional: number;
  bauspar_loan: number;
  loan_to_bauspar_ratio: number;
  is_bridge_loan: boolean;
  allocation_estimated: boolean;
  allocation_in_past: boolean;
  repayment_active: boolean;
  saving_after_allocation: boolean;
  warn_loan_pointless: boolean;
  contract_start_date: number;
  first_payment_date: number;
  allocation_date: number;
  loan_start_date: number;
  contract_end_date: number;
  year_contract: string;
  year_first_payment: string;
  year_allocation: string;
  year_loan_start: string;
  x_contract: number;
  x_first_payment: number;
  x_allocation: number;
  x_loan_start: number;
  x_now: number;
  /**
   * Not published. Kept for the precondition reports, which must derive their
   * explanation from the data at the point of the finding (R14) and several of
   * which ask about values the record deliberately does not carry -- for
   * example whether the contract end was observed or was the chained fallback
   * of C6, which is exactly the trace finding FND-08 says the unit does not
   * leave. None of this reaches a checkpoint object.
   */
  unrounded: {
    savings_ratio: number;
    loan_to_bauspar_ratio: number;
    saving_reference: number;
    balance: number;
    bauspar_loan: number;
    over_goal: boolean;
    contract_ended: boolean;
    saving_progress: number;
    goal_fraction: number;
    tariff_value: number;
    contract_end_estimated: boolean;
    parsed_start: number;
    parsed_first_payment: number;
    parsed_allocation: number;
    parsed_repayment: number;
    parsed_end: number;
  };
}

function readDateField(f: DateInput, rowIndex: number): number {
  if (f.coerced) return f.day;
  if (f.text === null) return NaN;
  return readDateText(f.text, f.column, rowIndex).day;
}

function readAmountField(text: string | null): number {
  if (text === null) return NaN;
  return readAmountText(text).value;
}

/**
 * Behaviour steps C0 through C19: one contract row and one valuation date in,
 * one record of exactly 33 named values out.
 */
export function computeContract(
  row: RawRow,
  valuationDay: number,
  cfg: EngineConfig,
  rowIndex: number,
): ContractRecord {
  // C3 -- read the five dates by rule C1, in the unit's own order.
  const rawStart = readDateField(row.abschlussdatum, rowIndex);
  const firstPayment = readDateField(row.einloesungsdatum, rowIndex);
  const rawAlloc = readDateField(row.erstmalige, rowIndex);
  const repaymentStart = readDateField(row.tilgungsbeginn, rowIndex);
  const rawEnd = readDateField(row.vertragsende, rowIndex);

  // C4 -- timeline origin.
  let contractStart = rawStart;
  if (Number.isNaN(contractStart)) contractStart = firstPayment;
  if (Number.isNaN(contractStart)) contractStart = valuationDay - cfg.fallbackOriginDays;

  // C5 -- allocation date. FND-08: this fallback chains into C6.
  const allocationEstimated = Number.isNaN(rawAlloc);
  let allocationDate: number;
  if (allocationEstimated) {
    const base = Number.isNaN(firstPayment) ? contractStart : firstPayment;
    allocationDate = base + cfg.allocationFallbackDays;
  } else {
    allocationDate = rawAlloc;
  }

  // C6 -- contract end (FND-08: chained on the estimate above, unmarked).
  const contractEndEstimated = Number.isNaN(rawEnd);
  const contractEnd = contractEndEstimated ? allocationDate + cfg.contractEndFallbackDays : rawEnd;

  // C7 -- amounts by rule C2. The Bauspar sum is in THOUSANDS of euro (P-13).
  const loanNotional = readAmountField(row.daBetrag);
  const bausparSum = readAmountField(row.bausparsummeTeuro) * BAUSPAR_SUM_UNIT_FACTOR;
  const balance = readAmountField(row.guthaben);

  // C8 -- tariff share. FND-02: used as a FRACTION OF ONE, whatever its magnitude.
  const tariff = row.tariffPresent ? readAmountField(row.tariffAmount) : NaN;
  let goalFraction: number;
  let goalSource: string;
  if (cfg.preferTariffShare && Number.isFinite(tariff) && tariff > 0) {
    goalFraction = tariff;
    goalSource = "tariff";
  } else {
    goalFraction = cfg.savingGoalFractionDefault;
    goalSource = "fallback_no_tariff";
  }

  // C9 -- contract type, unchanged and untrimmed, empty text included.
  const contractType = row.contractTypePresent ? row.contractType : null;

  // C10 -- bridge test, on the UNROUNDED ratio, STRICTLY greater than the cutoff.
  const ratio = Number.isFinite(bausparSum) && bausparSum > 0 ? loanNotional / bausparSum : NaN;
  const isBridgeLoan = Number.isFinite(ratio) && ratio > cfg.bridgeRatioCutoff;

  // C11 -- saving reference.
  const savingReference =
    isBridgeLoan && Number.isFinite(bausparSum) && bausparSum > 0 ? bausparSum : loanNotional;

  // C12 -- derived amounts. The warning flag is decided here, BEFORE C19 rounds
  // the ratio it is decided from. That disagreement is FND-13 and is deliberate.
  const savingGoal = goalFraction * savingReference;
  const savingsRatio =
    Number.isFinite(savingReference) && savingReference > 0 ? balance / savingReference : NaN;
  const bausparLoan = savingReference - balance;
  const warnLoanPointless = Number.isFinite(savingsRatio) && savingsRatio >= cfg.warnBalanceFraction;

  // C13 -- timeline predicates, each with the strictness the spec states.
  const allocationInPast = !Number.isNaN(allocationDate) && valuationDay > allocationDate;
  const repaymentActive = !Number.isNaN(repaymentStart) && valuationDay >= repaymentStart;
  const contractEnded = !Number.isNaN(contractEnd) && valuationDay >= contractEnd;
  const overGoal = Number.isFinite(savingsRatio) && savingsRatio >= goalFraction;

  // C14 -- phase, in this order of precedence.
  let phase: string;
  if (contractEnded) phase = "done";
  else if (repaymentActive) phase = "loan";
  else phase = overGoal ? "oversave" : "save";

  // C15
  const savingAfterAllocation = allocationInPast && !repaymentActive && !contractEnded;

  // C16 -- schematic positions and saving progress.
  const savingProgress = Number.isFinite(savingsRatio) ? clamp01(savingsRatio / goalFraction, 0, 1) : 0;

  // C17 -- current position, exactly one of three branches.
  let xLoanStart: number;
  let xNow: number;
  if (phase === "loan" || phase === "done") {
    xLoanStart = AXIS_ALLOCATION;
    const ref = Number.isNaN(repaymentStart) ? allocationDate : repaymentStart;
    const window = contractEnd - ref;
    const elapsed = valuationDay - ref;
    const progress = Number.isFinite(window) && window > 0 ? clamp01(elapsed / window, 0, 1) : 0;
    xNow = AXIS_ALLOCATION + progress * LOAN_REGION_WIDTH;
  } else if (savingAfterAllocation) {
    xLoanStart = NaN;
    const window = allocationDate - firstPayment;
    const extra = valuationDay - allocationDate;
    const frac = Number.isFinite(window) && window > 0 ? clamp01(extra / window, 0, 1) : 0;
    xNow = AXIS_ALLOCATION + frac * FORTSETZER_WEDGE;
  } else {
    xLoanStart = NaN;
    xNow = AXIS_FIRST_PAYMENT + savingProgress * SAVING_REGION_WIDTH;
    if (phase === "oversave") xNow = Math.min(xNow + OVERSAVE_BUMP, OVERSAVE_CAP);
  }

  // C18 -- year labels, with the tilde on an estimated allocation.
  const yearContract = yearLabel(contractStart);
  const yearFirstPayment = yearLabel(firstPayment);
  let yearAllocation = yearLabel(allocationDate);
  const yearLoanStart = yearLabel(repaymentStart);
  if (allocationEstimated && yearAllocation !== "") yearAllocation = "~" + yearAllocation;

  // C19 -- the record. Rounding happens ONLY here; every decision above was
  // taken on the unrounded value (FND-13).
  return {
    id: row.bsv,
    phase,
    savings_ratio: roundRecord(savingsRatio, ROUNDING_PLACES["savings_ratio"]!),
    saving_goal: roundRecord(savingGoal, ROUNDING_PLACES["saving_goal"]!),
    contract_type: contractType,
    goal_fraction: roundRecord(goalFraction, ROUNDING_PLACES["goal_fraction"]!),
    goal_source: goalSource,
    saving_reference: roundRecord(savingReference, ROUNDING_PLACES["saving_reference"]!),
    balance: roundRecord(balance, ROUNDING_PLACES["balance"]!),
    bauspar_sum: roundRecord(bausparSum, ROUNDING_PLACES["bauspar_sum"]!),
    loan_notional: roundRecord(loanNotional, ROUNDING_PLACES["loan_notional"]!),
    bauspar_loan: roundRecord(bausparLoan, ROUNDING_PLACES["bauspar_loan"]!),
    loan_to_bauspar_ratio: roundRecord(ratio, ROUNDING_PLACES["loan_to_bauspar_ratio"]!),
    is_bridge_loan: isBridgeLoan,
    allocation_estimated: allocationEstimated,
    allocation_in_past: allocationInPast,
    repayment_active: repaymentActive,
    saving_after_allocation: savingAfterAllocation,
    warn_loan_pointless: warnLoanPointless,
    contract_start_date: contractStart,
    first_payment_date: firstPayment,
    allocation_date: allocationDate,
    loan_start_date: repaymentStart,
    contract_end_date: contractEnd,
    year_contract: yearContract,
    year_first_payment: yearFirstPayment,
    year_allocation: yearAllocation,
    year_loan_start: yearLoanStart,
    x_contract: roundRecord(AXIS_CONTRACT, ROUNDING_PLACES["x_contract"]!),
    x_first_payment: roundRecord(AXIS_FIRST_PAYMENT, ROUNDING_PLACES["x_first_payment"]!),
    x_allocation: roundRecord(AXIS_ALLOCATION, ROUNDING_PLACES["x_allocation"]!),
    x_loan_start: roundRecord(xLoanStart, ROUNDING_PLACES["x_loan_start"]!),
    x_now: roundRecord(xNow, ROUNDING_PLACES["x_now"]!),
    unrounded: {
      savings_ratio: savingsRatio,
      loan_to_bauspar_ratio: ratio,
      saving_reference: savingReference,
      balance,
      bauspar_loan: bausparLoan,
      over_goal: overGoal,
      contract_ended: contractEnded,
      saving_progress: savingProgress,
      goal_fraction: goalFraction,
      tariff_value: tariff,
      contract_end_estimated: contractEndEstimated,
      parsed_start: rawStart,
      parsed_first_payment: firstPayment,
      parsed_allocation: rawAlloc,
      parsed_repayment: repaymentStart,
      parsed_end: rawEnd,
    },
  };
}

// --- C21 EXPORT MAPPING ------------------------------------------------------

export type ExportValue = string | number | null;

/**
 * Behaviour step C21: the record renamed and narrowed to the 25 export names.
 *
 * FND-05 lives in `special`: the alarm is decided on the PUBLISHED, ALREADY
 * ROUNDED ratio with a cutoff of 0.5 written into this mapping, while `bridge`
 * was decided in C10 on the UNROUNDED ratio against a configurable cutoff of 2.
 * The two are deliberately not derived from each other.
 */
export function mapExport(r: ContractRecord): ExportValue[] {
  const rounded = r.loan_to_bauspar_ratio;
  const special = Number.isFinite(rounded) && rounded < SPECIAL_ALARM_RATIO_CUTOFF ? 1 : 0;
  return [
    r.id,                       // id
    r.phase,                    // phase
    r.warn_loan_pointless ? 1 : 0,   // warn
    r.savings_ratio,            // sr
    r.x_contract,               // xc
    r.x_first_payment,          // xf
    r.x_allocation,             // xa
    r.x_loan_start,             // xl
    r.x_now,                    // xn
    r.year_contract,            // lab_contract
    r.year_first_payment,       // lab_first
    r.year_allocation,          // lab_alloc
    r.year_loan_start,          // lab_loan
    r.balance,                  // guthaben
    r.bauspar_sum,              // bausparsumme
    r.saving_goal,              // save_target
    r.bauspar_loan,             // loan_amount   (FND-09: rounded independently)
    r.loan_notional,            // dabetrag
    r.allocation_estimated ? 1 : 0,  // alloc_est
    r.loan_to_bauspar_ratio,    // da_bsum_ratio
    r.is_bridge_loan ? 1 : 0,   // bridge
    r.goal_fraction,            // goal_frac
    r.contract_type,            // contract_type
    r.goal_source,              // goal_source
    special,                    // special
  ];
}
