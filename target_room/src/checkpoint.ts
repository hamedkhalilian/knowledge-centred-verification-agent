// src/checkpoint.ts
//
// Canonicalisation contract `dec9-half-even-v1`, sections 2, 3, 5 and 6:
// canonical row order, column rendering, column and object digests, the three
// probes, and the five coverage fields.
//
// Every rule here is the contract's, not a convenience:
//   * row order is CONTRACTUAL and is applied before serialisation;
//   * NA sorts last regardless of direction;
//   * columns are digested in DECLARED SPEC ORDER, not alphabetical;
//   * a digest is an object carrying its algorithm and canonicalisation, never
//     a bare string (R12);
//   * a probe without its selection_rule is invalid (R12);
//   * all five coverage fields are always present, null when untracked, because
//     an absent field and a tracked zero are different claims (R12).

import * as crypto from "node:crypto";
import * as fs from "node:fs";
import {
  canonicalNumber, canonicalDate, canonicalLogical, canonicalString, intText,
} from "./canonical.js";
import { type Column, type ObjectStore, columnLength } from "./store.js";

export interface OrderKey {
  column: string;
  direction: "asc" | "desc";
}

export interface DigestObject {
  algorithm: "SHA-256";
  canonicalisation: "dec9-half-even-v1";
  value: string;
}

export interface Probe {
  selection_rule: string;
  fields: Record<string, string>;
}

export interface Coverage {
  row_count: number | null;
  field_count: number | null;
  null_count: number | null;
  min: string | null;
  max: string | null;
}

export interface CheckpointObject {
  name: string;
  kind: "frame" | "series" | "scalar" | "keyed_list";
  rows: number | null;
  cols: number | null;
  colnames: string[];
  canonical_order: OrderKey[];
  digest: DigestObject;
  coverage: Coverage;
  probes: Probe[];
}

export function canonicalCell(c: Column, i: number): string {
  switch (c.kind) {
    case "num":
      return canonicalNumber(c.num!.get(i));
    case "date":
      return canonicalDate(c.num!.get(i));
    case "bool": {
      const v = c.bool!.get(i);
      return canonicalLogical(v < 0 ? null : v === 1);
    }
    case "str":
      return canonicalString(c.str![i]!);
  }
}

function isNullCell(c: Column, i: number): boolean {
  switch (c.kind) {
    case "num":
    case "date":
      return Number.isNaN(c.num!.get(i));
    case "bool":
      return c.bool!.get(i) < 0;
    case "str":
      return c.str![i] === null;
  }
}

function sha256(parts: string): string {
  return crypto.createHash("sha256").update(Buffer.from(parts, "utf8")).digest("hex");
}

/** Canonicalisation contract §2, column rendering and column digest. */
export function columnDigest(c: Column, order: Int32Array): string {
  const pieces: string[] = ["col", c.name, intText(order.length)];
  for (let k = 0; k < order.length; k++) pieces.push(canonicalCell(c, order[k]!));
  return sha256(pieces.join("\n"));
}

/** Canonicalisation contract §2, object digest, columns in DECLARED order. */
export function objectDigest(kind: string, rows: number, cols: number, colDigests: Array<[string, string]>): string {
  const pieces: string[] = ["obj", kind, intText(rows), intText(cols)];
  for (const [n, d] of colDigests) pieces.push(n + "=" + d);
  return sha256(pieces.join("\n"));
}

function findColumn(s: ObjectStore, name: string): Column {
  for (const c of s.columns) if (c.name === name) return c;
  throw new Error("canonical_order names a column that the object does not carry: " + name);
}

/**
 * Canonicalisation contract §2, row order. Stable, by the declared keys.
 * Numeric by value, strings bytewise as UTF-8, dates by epoch day. NA sorts last
 * regardless of direction.
 */
export function canonicalOrder(s: ObjectStore, keys: OrderKey[]): Int32Array {
  const n = columnLength(s.columns[0]!);
  const idx = new Int32Array(n);
  for (let i = 0; i < n; i++) idx[i] = i;

  const prepared = keys.map((k) => {
    const c = findColumn(s, k.column);
    let bytes: Buffer[] | null = null;
    if (c.kind === "str") {
      bytes = new Array<Buffer>(n);
      for (let i = 0; i < n; i++) bytes[i] = Buffer.from(c.str![i] ?? "", "utf8");
    }
    return { c, dir: k.direction === "desc" ? -1 : 1, bytes };
  });

  const arr = Array.from(idx);
  arr.sort((a, b) => {
    for (const p of prepared) {
      const na = isNullCell(p.c, a);
      const nb = isNullCell(p.c, b);
      if (na && nb) continue;
      if (na) return 1; // NA last, regardless of direction
      if (nb) return -1;
      let cmp: number;
      if (p.c.kind === "str") {
        cmp = Buffer.compare(p.bytes![a]!, p.bytes![b]!);
      } else {
        const va = p.c.num!.get(a);
        const vb = p.c.num!.get(b);
        cmp = va < vb ? -1 : va > vb ? 1 : 0;
      }
      if (cmp !== 0) return cmp * p.dir;
    }
    return 0;
  });
  return Int32Array.from(arr);
}

/** Canonicalisation contract §5: exactly three probes over the canonically sorted rows. */
export function makeProbes(s: ObjectStore, order: Int32Array): Probe[] {
  const n = order.length;
  if (n === 0) return [];
  const rules: Array<[string, number]> = [
    ["index:1", 0],
    ["index:ceil(n/2)", Math.ceil(n / 2) - 1],
    ["index:n", n - 1],
  ];
  return rules.map(([rule, pos]) => {
    const row = order[pos]!;
    const fields: Record<string, string> = {};
    for (const c of s.columns) fields[c.name] = canonicalCell(c, row);
    return { selection_rule: rule, fields };
  });
}

/**
 * Canonicalisation contract §6. min/max range over every NUMERIC cell of the
 * object. A date column is not a numeric column and a logical column is not a
 * numeric column; a frame with no numeric cell reports null for both.
 */
export function makeCoverage(s: ObjectStore): Coverage {
  const n = columnLength(s.columns[0]!);
  let nulls = 0;
  let min = Infinity;
  let max = -Infinity;
  let sawNumeric = false;
  for (const c of s.columns) {
    for (let i = 0; i < n; i++) {
      if (isNullCell(c, i)) {
        nulls += 1;
        continue;
      }
      if (c.kind === "num") {
        sawNumeric = true;
        const v = c.num!.get(i);
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
  }
  return {
    row_count: n,
    field_count: s.columns.length,
    null_count: nulls,
    min: sawNumeric ? canonicalNumber(min) : null,
    max: sawNumeric ? canonicalNumber(max) : null,
  };
}

export function buildCheckpointObject(s: ObjectStore, keys: OrderKey[]): CheckpointObject {
  const order = canonicalOrder(s, keys);
  const colDigests: Array<[string, string]> = s.columns.map((c) => [c.name, columnDigest(c, order)]);
  const rows = order.length;
  const cols = s.columns.length;
  return {
    name: s.name,
    kind: "frame",
    rows,
    cols,
    colnames: s.columns.map((c) => c.name),
    canonical_order: keys,
    digest: {
      algorithm: "SHA-256",
      canonicalisation: "dec9-half-even-v1",
      value: objectDigest("frame", rows, cols, colDigests),
    },
    coverage: makeCoverage(s),
    probes: makeProbes(s, order),
  };
}

/** Canonicalisation contract §7: every input file consumed, by name, size and digest. */
export function fileDigest(path: string): { bytes: number; sha256: string } {
  const h = crypto.createHash("sha256");
  let bytes = 0;
  // streamed, never read whole (GR-09)
  const fd = fs.openSync(path, "r");
  try {
    const buf = Buffer.alloc(1 << 16);
    for (;;) {
      const n = fs.readSync(fd, buf, 0, buf.length, null);
      if (n <= 0) break;
      h.update(buf.subarray(0, n));
      bytes += n;
    }
  } finally {
    fs.closeSync(fd);
  }
  return { bytes, sha256: h.digest("hex") };
}
