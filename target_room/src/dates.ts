// src/dates.ts
//
// Neutral spec behaviour step C1 (DATE READING RULE) and step C18 (YEAR LABELS),
// plus the epoch-day arithmetic the whole unit runs on.
//
// Dates are carried as EPOCH DAYS (days since 1970-01-01), which is also the
// canonicalisation contract's wire form for a date. NaN means missing.
//
// FND-06 is reproduced here in full and deliberately:
//   * a value containing a hyphen that is not a readable calendar date RAISES
//     an error that stops the whole run (DateParseAbort);
//   * a value with no hyphen that is not readable becomes missing, silently;
//   * the digit branch is NOT width-checked, so 2013112 reads as 2013-11-02;
//   * text after a complete eight-digit match is ignored, so 20110401.0 reads
//     as 2011-04-01;
//   * 2011/04/01 has no hyphen, goes to the digit branch and becomes missing.
//
// The scanners below are deliberately NON-BACKTRACKING, because the source's
// scanner is. A backtracking regular expression would read 2011/04/01 as
// year 20, month 1, day 1 instead of rejecting it, which is exactly the
// measured behaviour the spec says must not happen.

import { intText } from "./canonical.js";

/** The seven texts that mean "this event has not happened" (constant date_missing_markers). */
export const DATE_MISSING_MARKERS: readonly string[] = ["", "0", "00", "0000", "00000000", "NA", "<NA>"];

export class DateParseAbort extends Error {
  public readonly rawValue: string;
  /** the input column whose value triggered it (controller directive 01, Rule C) */
  public column: string;
  /** 1-based position of the offending row in the input table AS RECEIVED */
  public rowIndex: number;
  constructor(rawValue: string, column: string, rowIndex: number) {
    super("character string is not in a standard unambiguous format");
    this.name = "DateParseAbort";
    this.rawValue = rawValue;
    this.column = column;
    this.rowIndex = rowIndex;
  }
}

/** days-from-civil (proleptic Gregorian), Howard Hinnant's algorithm. */
export function daysFromCivil(y: number, m: number, d: number): number {
  const yy = y - (m <= 2 ? 1 : 0);
  const era = Math.floor(yy / 400);
  const yoe = yy - era * 400;
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

/** civil-from-days, the inverse of daysFromCivil. */
export function civilFromDays(z0: number): { y: number; m: number; d: number } {
  const z = z0 + 719468;
  const era = Math.floor(z / 146097);
  const doe = z - era * 146097;
  const yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524) - Math.floor(doe / 146096)) / 365);
  const y = yoe + era * 400;
  const doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
  const mp = Math.floor((5 * doy + 2) / 153);
  const d = doy - Math.floor((153 * mp + 2) / 5) + 1;
  const m = mp + (mp < 10 ? 3 : -9);
  return { y: y + (m <= 2 ? 1 : 0), m, d };
}

function isLeap(y: number): boolean {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}
const MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export function validCivil(y: number, m: number, d: number): boolean {
  if (!Number.isInteger(y) || y < 0) return false;
  if (m < 1 || m > 12) return false;
  if (d < 1) return false;
  const len = m === 2 && isLeap(y) ? 29 : MONTH_LENGTHS[m - 1];
  return d <= len;
}

/** A non-backtracking greedy digit scan of at most `max` digits, at least one. */
interface Scan {
  ok: boolean;
  value: number;
  pos: number;
}
function scanDigits(s: string, pos: number, max: number): Scan {
  let n = 0;
  let v = 0;
  while (n < max && pos < s.length) {
    const c = s.charCodeAt(pos);
    if (c < 0x30 || c > 0x39) break;
    v = v * 10 + (c - 0x30);
    pos++;
    n++;
  }
  if (n === 0) return { ok: false, value: 0, pos };
  return { ok: true, value: v, pos };
}

/**
 * "%Y<sep>%m<sep>%d" with a fixed separator, trailing text ignored.
 * Returns the epoch day, or null when the scan or the calendar check fails.
 */
function scanSeparated(text: string, sep: number): number | null {
  const y = scanDigits(text, 0, 4);
  if (!y.ok) return null;
  if (y.pos >= text.length || text.charCodeAt(y.pos) !== sep) return null;
  const m = scanDigits(text, y.pos + 1, 2);
  if (!m.ok) return null;
  if (m.pos >= text.length || text.charCodeAt(m.pos) !== sep) return null;
  const d = scanDigits(text, m.pos + 1, 2);
  if (!d.ok) return null;
  if (!validCivil(y.value, m.value, d.value)) return null;
  return daysFromCivil(y.value, m.value, d.value);
}

/**
 * The "standard unambiguous format" parse: "%Y-%m-%d" then "%Y/%m/%d".
 * This is what the hyphen branch of C1 uses, and what the harness's column-wide
 * coercion uses to infer a format from the first non-missing element.
 */
export function parseStandardUnambiguous(text: string): number | null {
  const a = scanSeparated(text, 0x2d /* - */);
  if (a !== null) return a;
  return scanSeparated(text, 0x2f /* / */);
}

/** Which of the two standard formats a text matches, or null. Used for column-wide coercion. */
export function detectStandardFormat(text: string): "%Y-%m-%d" | "%Y/%m/%d" | null {
  if (scanSeparated(text, 0x2d) !== null) return "%Y-%m-%d";
  if (scanSeparated(text, 0x2f) !== null) return "%Y/%m/%d";
  return null;
}

export function parseWithStandardFormat(text: string, fmt: "%Y-%m-%d" | "%Y/%m/%d"): number | null {
  return scanSeparated(text, fmt === "%Y-%m-%d" ? 0x2d : 0x2f);
}

/**
 * The digit branch of C1: "%Y%m%d" scanned greedily and without backtracking,
 * widths at most 4/2/2, trailing text ignored, no width check on the whole.
 */
export function parseEightDigits(text: string): number | null {
  const y = scanDigits(text, 0, 4);
  if (!y.ok) return null;
  const m = scanDigits(text, y.pos, 2);
  if (!m.ok) return null;
  const d = scanDigits(text, m.pos, 2);
  if (!d.ok) return null;
  if (!validCivil(y.value, m.value, d.value)) return null;
  return daysFromCivil(y.value, m.value, d.value);
}

export function isDateMissingMarker(trimmed: string): boolean {
  for (const m of DATE_MISSING_MARKERS) if (m === trimmed) return true;
  return false;
}

export interface DateReadOutcome {
  /** epoch day, or NaN for missing */
  day: number;
  /** how the value was classified, for the reconciliation report (R16/GR-08) */
  how: "already_date" | "marker" | "hyphen_ok" | "digits_ok" | "digits_failed_missing";
}

/**
 * Behaviour step C1 applied to ONE text value that the unit itself parses.
 * Throws DateParseAbort on an unreadable hyphenated value (FND-06).
 */
export function readDateText(raw: string, column: string, rowIndex: number): DateReadOutcome {
  const t = raw.trim();
  if (isDateMissingMarker(t)) return { day: NaN, how: "marker" };
  if (t.indexOf("-") >= 0) {
    const v = parseStandardUnambiguous(t);
    if (v === null) throw new DateParseAbort(raw, column, rowIndex);
    return { day: v, how: "hyphen_ok" };
  }
  const v = parseEightDigits(t);
  if (v === null) return { day: NaN, how: "digits_failed_missing" };
  return { day: v, how: "digits_ok" };
}

/** Behaviour step C18: an empty text when missing, otherwise the calendar year. */
export function yearLabel(day: number): string {
  if (Number.isNaN(day)) return "";
  const c = civilFromDays(day);
  let s = intText(c.y);
  while (s.length < 4) s = "0" + s;
  return s;
}

/** "year-month-day" rendering, used for the browser file's second comment line. */
export function renderIsoDate(day: number): string {
  const c = civilFromDays(day);
  const p2 = (n: number) => (n < 10 ? "0" + intText(n) : intText(n));
  let ys = intText(c.y);
  while (ys.length < 4) ys = "0" + ys;
  return ys + "-" + p2(c.m) + "-" + p2(c.d);
}
