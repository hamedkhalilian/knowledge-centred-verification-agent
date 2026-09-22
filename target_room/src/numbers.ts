// src/numbers.ts
//
// Neutral spec behaviour step C2 — the GERMAN NUMBER READING RULE, and the
// faithful reproduction of finding FND-01.
//
// The rule, verbatim in effect:
//   * an already-numeric value is used as it stands and NO missing marker
//     applies to it, so a numeric zero stays zero;
//   * otherwise the value is rendered as text, surrounding whitespace removed,
//     and the five markers of `amount_missing_markers` mean missing;
//   * otherwise: if the text CONTAINS A COMMA, every dot is deleted first (they
//     are thousands separators) and then the comma becomes the decimal point;
//     if the text contains no comma it is read as written, so a dot in it is a
//     decimal point;
//   * text that still does not read as a number becomes missing, silently.
//
// FND-01 lives in the third clause: "36.263" has no comma, so the dot is a
// decimal point and the value reads as 36.263, not 36263 -- a thousand times too
// small. That is the source's behaviour and it is reproduced, not repaired. The
// hazard is reported by precondition FND-01 in preconditions.ts instead.

/** The five texts that make an amount missing (constant amount_missing_markers). */
export const AMOUNT_MISSING_MARKERS: readonly string[] = ["", "NA", "<NA>", "n/a", "-"];

export function isAmountMissingMarker(trimmed: string): boolean {
  for (const m of AMOUNT_MISSING_MARKERS) if (m === trimmed) return true;
  return false;
}

/**
 * The numeric grammar accepted after the comma/dot transform. Modelled on the
 * source language's own text-to-number conversion: optional sign, decimal digits
 * with an optional point on either side, optional exponent; plus the infinities
 * and the not-a-number literal, which that conversion also accepts.
 */
const DECIMAL_RE = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
const INF_RE = /^[+-]?(Inf|inf|Infinity)$/;
const NAN_RE = /^[+-]?NaN$/;

export interface AmountReadOutcome {
  /** the value, or NaN for missing */
  value: number;
  how: "already_numeric" | "marker" | "comma_decimal" | "plain" | "unparsed_missing";
}

/** Behaviour step C2 applied to ONE text value. Never throws. */
export function readAmountText(raw: string): AmountReadOutcome {
  const t = raw.trim();
  if (isAmountMissingMarker(t)) return { value: NaN, how: "marker" };
  let body = t;
  let how: AmountReadOutcome["how"] = "plain";
  if (t.indexOf(",") >= 0) {
    body = t.split(".").join("").split(",").join(".");
    how = "comma_decimal";
  }
  if (DECIMAL_RE.test(body)) return { value: Number(body), how };
  if (INF_RE.test(body)) return { value: body.charCodeAt(0) === 0x2d ? -Infinity : Infinity, how };
  if (NAN_RE.test(body)) return { value: NaN, how };
  return { value: NaN, how: "unparsed_missing" };
}
