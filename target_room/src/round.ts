// src/round.ts
//
// Neutral spec behaviour step C20 — the rounding rule of the PUBLISHED RECORD.
// This is NOT the rendering rule of C22 (that lives in canonical.ts), and it is
// NOT "multiply by 10^d, round half-even in binary, divide back".
//
// Stated rule, verbatim from the spec:
//   work on the magnitude and put the sign back at the end, so a negative value
//   that rounds to zero yields a negative zero; let k be the largest integer not
//   greater than magnitude times ten-to-the-d, evaluated EXACTLY on the binary
//   value held, not in binary floating point; form the two candidate results as
//   the binary values nearest to the decimals k over ten-to-the-d and k plus one
//   over ten-to-the-d; compare the exact distances from the magnitude to each
//   candidate and take the nearer; if the two distances are exactly equal take
//   the candidate whose numerator is even. A missing or non-finite value is
//   returned unchanged.
//
// The sixteen measured reference vectors of constant `round_reference_vectors`
// are re-checked at startup by selftest.ts; the process aborts if any fails.

import { exactOf, decimalToNearestDouble } from "./canonical.js";

function pow10n(p: number): bigint {
  let r = 1n;
  for (let i = 0; i < p; i++) r *= 10n;
  return r;
}

/** Exact comparison of two non-negative rationals a1/b1 and a2/b2. */
function cmpRat(a1: bigint, b1: bigint, a2: bigint, b2: bigint): number {
  const l = a1 * b2;
  const r = a2 * b1;
  return l < r ? -1 : l > r ? 1 : 0;
}

/** Exact difference (a1/b1) - (a2/b2) as a normalised non-negative rational, caller guarantees a1/b1 >= a2/b2. */
function subRat(a1: bigint, b1: bigint, a2: bigint, b2: bigint): { n: bigint; d: bigint } {
  return { n: a1 * b2 - a2 * b1, d: b1 * b2 };
}

/**
 * Round a double to `places` decimal places under the rule of behaviour step C20.
 * NaN and the infinities are returned unchanged. Negative zero is produced for a
 * negative value whose magnitude rounds to zero.
 */
export function roundRecord(x: number, places: number): number {
  if (!Number.isFinite(x)) return x;
  const neg = x < 0 || Object.is(x, -0);
  const mag = Math.abs(x);
  if (mag === 0) return neg ? -0 : 0;

  const ev = exactOf(mag); // ev.neg is false here
  const p = pow10n(places);

  // k = floor(mag * 10^places), exactly
  const k = (ev.num * p) / ev.den;

  const c0 = decimalToNearestDouble(k, places);
  const c1 = decimalToNearestDouble(k + 1n, places);

  const e0 = exactOf(c0);
  const e1 = exactOf(c1);

  // d0 = mag - c0 (>= 0 because c0 is the nearest double to a value <= mag ...
  // not guaranteed: c0 may round UP past mag. Take absolute differences.)
  const cmp0 = cmpRat(ev.num, ev.den, e0.num, e0.den);
  const d0 =
    cmp0 >= 0
      ? subRat(ev.num, ev.den, e0.num, e0.den)
      : subRat(e0.num, e0.den, ev.num, ev.den);
  const cmp1 = cmpRat(e1.num, e1.den, ev.num, ev.den);
  const d1 =
    cmp1 >= 0
      ? subRat(e1.num, e1.den, ev.num, ev.den)
      : subRat(ev.num, ev.den, e1.num, e1.den);

  const c = cmpRat(d0.n, d0.d, d1.n, d1.d);
  let chosen: number;
  if (c < 0) chosen = c0;
  else if (c > 0) chosen = c1;
  else chosen = k % 2n === 0n ? c0 : c1;

  if (chosen === 0) return neg ? -0 : 0;
  return neg ? -chosen : chosen;
}

/** Clamp of behaviour step C16: smaller of value and upper, then larger of that and lower. */
export function clamp01(v: number, lo: number, hi: number): number {
  return Math.max(Math.min(v, hi), lo);
}
