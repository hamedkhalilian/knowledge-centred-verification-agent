// src/store.ts
//
// Column-oriented storage for the published objects.
//
// GR-09 / target directive 8: parsing streams into typed arrays. The staged
// stand-in is 503 rows; production is 45,881, and the whole-book object carries
// 34 columns. One boxed object per row would be 45,881 objects of 34 fields for
// customer_book alone, repeated for customer_export_rows. Columns of
// Float64Array / Int8Array cost a fixed 8 or 1 byte per cell instead.
//
// Missing values:
//   numeric and date columns use NaN. The canonicalisation contract renders NA
//   and NaN identically ("NA"), so NaN is a lossless in-memory marker for a
//   missing number, and a missing date is never a legitimate epoch day.
//   logical columns use -1 for NA, 0 for false, 1 for true.
//   text columns use null.

export class F64Vec {
  private buf: Float64Array;
  public length = 0;
  constructor(capacity = 1024) {
    this.buf = new Float64Array(capacity);
  }
  push(v: number): void {
    if (this.length === this.buf.length) {
      const next = new Float64Array(this.buf.length * 2);
      next.set(this.buf);
      this.buf = next;
    }
    this.buf[this.length++] = v;
  }
  get(i: number): number {
    return this.buf[i]!;
  }
  view(): Float64Array {
    return this.buf.subarray(0, this.length);
  }
}

export class I8Vec {
  private buf: Int8Array;
  public length = 0;
  constructor(capacity = 1024) {
    this.buf = new Int8Array(capacity);
  }
  push(v: number): void {
    if (this.length === this.buf.length) {
      const next = new Int8Array(this.buf.length * 2);
      next.set(this.buf);
      this.buf = next;
    }
    this.buf[this.length++] = v;
  }
  get(i: number): number {
    return this.buf[i]!;
  }
}

export type ColumnKind = "num" | "str" | "bool" | "date";

export interface Column {
  name: string;
  kind: ColumnKind;
  num?: F64Vec;
  str?: (string | null)[];
  bool?: I8Vec;
}

export function makeColumn(name: string, kind: ColumnKind): Column {
  if (kind === "str") return { name, kind, str: [] };
  if (kind === "bool") return { name, kind, bool: new I8Vec() };
  return { name, kind, num: new F64Vec() };
}

export function columnLength(c: Column): number {
  if (c.kind === "str") return c.str!.length;
  if (c.kind === "bool") return c.bool!.length;
  return c.num!.length;
}

export interface ObjectStore {
  name: string;
  kind: "frame";
  columns: Column[];
}

export function makeStore(name: string, spec: Array<[string, ColumnKind]>): ObjectStore {
  return { name, kind: "frame", columns: spec.map(([n, k]) => makeColumn(n, k)) };
}

export function pushNum(s: ObjectStore, i: number, v: number): void {
  s.columns[i]!.num!.push(v);
}
export function pushStr(s: ObjectStore, i: number, v: string | null): void {
  s.columns[i]!.str!.push(v);
}
export function pushBool(s: ObjectStore, i: number, v: boolean | null): void {
  s.columns[i]!.bool!.push(v === null ? -1 : v ? 1 : 0);
}

/**
 * Neumaier (improved Kahan) compensated summation.
 *
 * Canonicalisation contract §8: the source accumulates statistical reductions in
 * extended precision, and plain double accumulation in the target may differ
 * near the ninth significant digit. This is an EMULATION of the source's
 * accumulator width, not an improvement on it (GR-11). Nothing that feeds a
 * checkpoint digest is produced by a summation in this build -- every published
 * value is a per-contract arithmetic expression -- so this is used only by the
 * precondition reports. That fact is recorded rather than assumed.
 */
export function neumaierSum(values: ArrayLike<number>, skipNaN: boolean): number {
  let sum = 0;
  let c = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i]!;
    if (skipNaN && Number.isNaN(v)) continue;
    const t = sum + v;
    if (Math.abs(sum) >= Math.abs(v)) c += sum - t + v;
    else c += v - t + sum;
    sum = t;
  }
  return sum + c;
}
