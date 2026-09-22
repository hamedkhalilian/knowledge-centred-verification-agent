// src/canonical.ts
//
// THE ONLY MODULE IN THIS PROJECT THAT FORMATS A NUMBER FOR OUTPUT.
// Target directive 3. A build-time scan (tools/scan_number_formatting.mjs)
// proves that no other module under src/ calls toFixed / toPrecision /
// toExponential / Intl.NumberFormat or otherwise renders a number.
//
// Two DIFFERENT renderings live here and they are not interchangeable:
//
//   1. canonicalNumber()  -- canonicalisation contract `dec9-half-even-v1`:
//      9 significant digits, round HALF-EVEN with respect to the EXACT decimal
//      expansion of the IEEE-754 binary value, format [-]d.dddddddde{+|-}XX.
//
//   2. scriptNumber()     -- neutral spec behaviour step C22: plain fixed
//      notation with exactly six digits after the point, half-even on the exact
//      binary value (the ordinary C "%.6f" conversion), then trailing zeros and
//      then a trailing decimal point removed.
//
// Both are exact: every decision is taken in BigInt arithmetic on the exact
// rational value of the double, never in binary floating point.

/** Exact rational value of a finite double: num / den, den a power of two, sign separate. */
export interface ExactValue {
  neg: boolean;
  num: bigint; // >= 0
  den: bigint; // > 0
}

const SCRATCH = new DataView(new ArrayBuffer(8));

/** Decompose a finite double into its exact rational value. */
export function exactOf(x: number): ExactValue {
  SCRATCH.setFloat64(0, x);
  const hi = SCRATCH.getUint32(0);
  const lo = SCRATCH.getUint32(4);
  const neg = (hi >>> 31) === 1;
  const biased = (hi >>> 20) & 0x7ff;
  let mant = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo >>> 0);
  let e: number;
  if (biased === 0) {
    e = -1074; // subnormal
  } else {
    mant |= 1n << 52n;
    e = biased - 1075;
  }
  if (e >= 0) return { neg, num: mant << BigInt(e), den: 1n };
  return { neg, num: mant, den: 1n << BigInt(-e) };
}

const TEN = 10n;
function pow10(p: number): bigint {
  let r = 1n;
  for (let i = 0; i < p; i++) r *= TEN;
  return r;
}

/**
 * Round the non-negative rational n/d to an integer, half-even.
 * Both arguments must be positive (d > 0, n >= 0).
 */
export function roundHalfEvenRational(n: bigint, d: bigint): bigint {
  const q = n / d;
  const r = n % d;
  const twice = r * 2n;
  if (twice > d) return q + 1n;
  if (twice < d) return q;
  return q % 2n === 0n ? q : q + 1n;
}

/** Exact comparison of |x| (as num/den) against 10^e. Returns -1, 0 or 1. */
function cmpAgainstPow10(num: bigint, den: bigint, e: number): number {
  // num/den  vs  10^e
  let left = num;
  let right = den;
  if (e >= 0) right = den * pow10(e);
  else left = num * pow10(-e);
  return left < right ? -1 : left > right ? 1 : 0;
}

/** floor(log10(|x|)) computed exactly for a finite non-zero double. */
function decimalExponent(num: bigint, den: bigint, approx: number): number {
  let e = Math.floor(Math.log10(approx));
  if (!Number.isFinite(e)) e = 0;
  // correct downwards
  while (cmpAgainstPow10(num, den, e) < 0) e -= 1;
  // correct upwards
  while (cmpAgainstPow10(num, den, e + 1) >= 0) e += 1;
  return e;
}

export const CANONICAL_NA = "NA";
export const CANONICAL_ZERO = "0.00000000e+00";

/**
 * Canonicalisation contract §1, finite-double row:
 * 9 significant digits, round half-even on the exact decimal expansion,
 * format [-]d.dddddddde{+|-}XX with the exponent sign always present and at
 * least two exponent digits. Exact zero and negative zero both render as the
 * positive form. NA/NaN render as "NA"; the infinities as INF / -INF.
 */
export function canonicalNumber(x: number | null | undefined): string {
  if (x === null || x === undefined) return CANONICAL_NA;
  if (Number.isNaN(x)) return CANONICAL_NA;
  if (x === Infinity) return "INF";
  if (x === -Infinity) return "-INF";
  if (x === 0) return CANONICAL_ZERO; // covers -0 as well: "negative zero renders as the positive form"

  const ev = exactOf(x);
  const abs = Math.abs(x);
  let e = decimalExponent(ev.num, ev.den, abs);

  // scale so the rounded integer has exactly 9 digits
  const shift = 8 - e;
  let n = ev.num;
  let d = ev.den;
  if (shift >= 0) n = n * pow10(shift);
  else d = d * pow10(-shift);
  let s = roundHalfEvenRational(n, d);
  const TEN9 = 1000000000n;
  if (s >= TEN9) {
    // rounding carried into a new decade, e.g. 9.999999995 -> 1.00000000e+01
    e += 1;
    const shift2 = 8 - e;
    let n2 = ev.num;
    let d2 = ev.den;
    if (shift2 >= 0) n2 = n2 * pow10(shift2);
    else d2 = d2 * pow10(-shift2);
    s = roundHalfEvenRational(n2, d2);
  }
  const digits = s.toString();
  const mantissa = digits[0] + "." + digits.slice(1);
  const esign = e < 0 ? "-" : "+";
  let eabs = Math.abs(e).toString();
  if (eabs.length < 2) eabs = "0" + eabs;
  return (ev.neg ? "-" : "") + mantissa + "e" + esign + eabs;
}

/**
 * Neutral spec behaviour step C22, numeric branch: exactly six digits after the
 * decimal point, half-even on the exact binary value (C "%.6f"), then trailing
 * zeros removed and then a trailing decimal point removed. A non-finite value
 * is the caller's problem (it renders as `null` there). Negative zero, and any
 * negative value that rounds to zero, renders as "-0".
 */
export function scriptNumber(x: number): string {
  const neg = x < 0 || Object.is(x, -0);
  if (x === 0) return neg ? "-0" : "0";
  const ev = exactOf(x);
  const s = roundHalfEvenRational(ev.num * pow10(6), ev.den);
  let digits = s.toString();
  while (digits.length < 7) digits = "0" + digits;
  const intPart = digits.slice(0, digits.length - 6);
  let frac = digits.slice(digits.length - 6);
  while (frac.length > 0 && frac[frac.length - 1] === "0") frac = frac.slice(0, frac.length - 1);
  const body = frac.length > 0 ? intPart + "." + frac : intPart;
  return (neg ? "-" : "") + body;
}

/**
 * Integer-to-text for counts, indices and epoch days. Routed through this module
 * so the build-time "no number formatting outside canonical.ts" scan can be
 * exact rather than approximate.
 */
export function intText(n: number): string {
  if (!Number.isFinite(n)) return CANONICAL_NA;
  return BigInt(Math.trunc(n)).toString();
}

/** Canonicalisation contract §1, date row: epoch days as decimal integer text. */
export function canonicalDate(epochDay: number | null): string {
  if (epochDay === null || Number.isNaN(epochDay)) return CANONICAL_NA;
  return intText(epochDay);
}

/** Canonicalisation contract §1, logical row. */
export function canonicalLogical(b: boolean | null): string {
  if (b === null) return CANONICAL_NA;
  return b ? "true" : "false";
}

/**
 * Canonicalisation contract §1, string row: exactly three escapes,
 * `\` -> `\\`, LF -> `\n`, CR -> `\r`. No trimming, no case folding.
 */
export function canonicalString(s: string | null): string {
  if (s === null) return CANONICAL_NA;
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c === 0x5c) out += "\\\\";
    else if (c === 0x0a) out += "\\n";
    else if (c === 0x0d) out += "\\r";
    else out += s[i];
  }
  return out;
}

/**
 * Neutral spec behaviour step C22, text branch: every backslash doubled, every
 * double quote prefixed with a backslash, wrapped in double quotes. No other
 * character is escaped. (This is NOT the canonicalisation string rule above.)
 */
export function scriptString(s: string): string {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c === 0x5c) out += "\\\\";
    else if (c === 0x22) out += '\\"';
    else out += s[i];
  }
  return '"' + out + '"';
}

/**
 * The binary double nearest to the exact decimal k / 10^d.
 *
 * Lives in this module because it builds decimal text from an integer, and this
 * module is the one place allowed to turn numbers into decimal text. It is used
 * by round.ts to form the two candidates of behaviour step C20.
 *
 * Number(string) is correctly rounded (IEEE-754 nearest-even) by the ECMAScript
 * specification, so the text -> double step introduces no error of its own, and
 * the text it is given is the EXACT decimal k/10^d, not an approximation.
 */
export function decimalToNearestDouble(k: bigint, d: number): number {
  if (d === 0) return Number(k.toString());
  let s = k.toString();
  while (s.length <= d) s = "0" + s;
  const whole = s.slice(0, s.length - d);
  const frac = s.slice(s.length - d);
  return Number(whole + "." + frac);
}
