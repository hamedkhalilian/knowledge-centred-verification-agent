// src/csv.ts
//
// A streaming, quote-aware delimited-text reader, plus the content-based layout
// detection required by GR-07 and R5.
//
// GR-09 / target directive 8: the staged stand-in is 503 rows but production is
// 45,881. Nothing here reads the file whole. The reader pulls fixed-size blocks
// with readSync, decodes them incrementally, and hands one record at a time to a
// callback; the caller keeps column arrays, never a table of parsed row objects.
//
// The quote handling is not decoration. The stand-in carries quoted fields that
// CONTAIN the delimiter on 103 of its 503 data lines; a reader that split lines
// on the delimiter would see 14 or 15 fields there and mis-assign every field
// after the first amount, silently. The controller's own profiler made exactly
// that mistake. That is a hazard this module verifies (see detectLayout), never
// a setting it adopts.

import * as fs from "node:fs";
import { intText } from "./canonical.js";

const BLOCK = 1 << 16;

/** Stream a file's bytes through a callback, block by block. */
export function streamBytes(path: string, onBlock: (b: Buffer, n: number) => void): void {
  const fd = fs.openSync(path, "r");
  try {
    const buf = Buffer.alloc(BLOCK);
    for (;;) {
      const n = fs.readSync(fd, buf, 0, BLOCK, null);
      if (n <= 0) break;
      onBlock(buf, n);
    }
  } finally {
    fs.closeSync(fd);
  }
}

export interface CsvOptions {
  delimiter: string;
  quote: string;
}

export interface CsvStats {
  /** number of records produced, header included */
  records: number;
  /** number of PHYSICAL lines in the file body (terminator-separated) */
  physicalLines: number;
  /** records whose parse consumed a quoted field that contained the delimiter */
  recordsWithQuotedDelimiter: number;
  /** distribution of field counts across records */
  fieldCountHistogram: Map<number, number>;
  /** true if the byte stream decoded as strict UTF-8 */
  utf8Strict: boolean;
  byteOrderMark: boolean;
  /** line terminators seen */
  crlf: number;
  lf: number;
}

/**
 * Parse a delimited file, calling `onRecord` for each record.
 * Return false from `onRecord` to stop early.
 */
export function parseCsv(
  path: string,
  opts: CsvOptions,
  onRecord: (fields: string[], recordIndex: number, quotedDelimiter: boolean) => boolean | void,
): CsvStats {
  const delim = opts.delimiter;
  const quote = opts.quote;
  const stats: CsvStats = {
    records: 0,
    physicalLines: 0,
    recordsWithQuotedDelimiter: 0,
    fieldCountHistogram: new Map<number, number>(),
    utf8Strict: true,
    byteOrderMark: false,
    crlf: 0,
    lf: 0,
  };

  const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false });
  let fields: string[] = [];
  let field = "";
  let inQuotes = false;
  let quoteJustClosed = false;
  let quotedDelimiter = false;
  let pendingCR = false;
  let first = true;
  let stopped = false;
  let sawAnyContent = false;

  const endField = () => {
    fields.push(field);
    field = "";
  };
  const endRecord = () => {
    endField();
    const n = fields.length;
    stats.fieldCountHistogram.set(n, (stats.fieldCountHistogram.get(n) ?? 0) + 1);
    if (quotedDelimiter) stats.recordsWithQuotedDelimiter += 1;
    const r = onRecord(fields, stats.records, quotedDelimiter);
    stats.records += 1;
    fields = [];
    quotedDelimiter = false;
    sawAnyContent = false;
    if (r === false) stopped = true;
  };

  const feed = (text: string) => {
    for (let i = 0; i < text.length && !stopped; i++) {
      const ch = text[i]!;
      if (first) {
        first = false;
        if (ch === "﻿") {
          stats.byteOrderMark = true;
          continue;
        }
      }
      if (pendingCR) {
        pendingCR = false;
        if (ch === "\n") {
          stats.crlf += 1;
          stats.physicalLines += 1;
          endRecord();
          continue;
        }
        // a lone CR inside the data; treat it as a record terminator too
        stats.physicalLines += 1;
        endRecord();
        if (stopped) break;
      }
      if (inQuotes) {
        if (quoteJustClosed) {
          quoteJustClosed = false;
          if (ch === quote) {
            field += quote; // doubled quote inside a quoted field
            sawAnyContent = true;
            continue;
          }
          inQuotes = false;
          // fall through and reprocess this character outside quotes
        } else {
          if (ch === quote) {
            quoteJustClosed = true;
            continue;
          }
          if (ch === delim) quotedDelimiter = true;
          field += ch;
          sawAnyContent = true;
          continue;
        }
      }
      if (ch === quote && field.length === 0) {
        inQuotes = true;
        sawAnyContent = true;
        continue;
      }
      if (ch === delim) {
        endField();
        sawAnyContent = true;
        continue;
      }
      if (ch === "\r") {
        pendingCR = true;
        continue;
      }
      if (ch === "\n") {
        stats.lf += 1;
        stats.physicalLines += 1;
        endRecord();
        continue;
      }
      field += ch;
      sawAnyContent = true;
    }
  };

  try {
    streamBytes(path, (b, n) => {
      if (stopped) return;
      feed(decoder.decode(b.subarray(0, n), { stream: true }));
    });
    if (!stopped) feed(decoder.decode());
  } catch (e) {
    if (e instanceof TypeError) stats.utf8Strict = false;
    else throw e;
  }
  if (!stopped && (sawAnyContent || field.length > 0 || fields.length > 0)) {
    // a final record with no trailing newline
    endRecord();
  }
  return stats;
}

// ---------------------------------------------------------------------------
// Content-based layout detection (GR-07, R5). Every anchor below is found from
// what the file CONTAINS. The neutral spec's io_formats block is NOT consulted
// here; it is compared against this reading afterwards, by iocheck.ts.
// ---------------------------------------------------------------------------

export interface DelimiterCandidate {
  delimiter: string;
  label: string;
  modalFieldCount: number;
  recordsAtModal: number;
  recordsSampled: number;
  score: number;
}

export interface LayoutReading {
  encoding: { utf8Strict: boolean; byteOrderMark: boolean };
  delimiter: { winner: DelimiterCandidate; runnerUp: DelimiterCandidate | null; margin: number };
  headerRow: { index: number; score: number; runnerUpScore: number; margin: number; names: string[] };
  fieldCountHistogram: Map<number, number>;
  dataRecords: number;
  recordsWithQuotedDelimiter: number;
  lineTerminators: { lf: number; crlf: number };
  note: string;
}

const DELIMITER_CANDIDATES: Array<{ ch: string; label: string }> = [
  { ch: ",", label: "comma" },
  { ch: ";", label: "semicolon" },
  { ch: "\t", label: "tab" },
  { ch: "|", label: "pipe" },
];

const SAMPLE_RECORDS = 200;

function scoreDelimiter(path: string, ch: string, label: string): DelimiterCandidate {
  const counts = new Map<number, number>();
  let sampled = 0;
  parseCsv(path, { delimiter: ch, quote: '"' }, (fields) => {
    counts.set(fields.length, (counts.get(fields.length) ?? 0) + 1);
    sampled += 1;
    return sampled < SAMPLE_RECORDS;
  });
  let modal = 1;
  let modalN = 0;
  for (const [k, v] of counts) {
    if (v > modalN || (v === modalN && k > modal)) {
      modal = k;
      modalN = v;
    }
  }
  // A delimiter earns points for splitting AND for splitting consistently.
  const score = modal <= 1 ? 0 : modalN * (modal - 1);
  return { delimiter: ch, label, modalFieldCount: modal, recordsAtModal: modalN, recordsSampled: sampled, score };
}

/** Header-ness of a record relative to the records under it. */
function headerScore(candidate: string[], body: string[][]): number {
  if (candidate.length === 0) return 0;
  let textCells = 0;
  let uniqueCells = 0;
  const seen = new Set<string>();
  for (const c of candidate) {
    const t = c.trim();
    if (t.length > 0 && !/^[+-]?[\d.,]+$/.test(t)) textCells += 1;
    if (!seen.has(t)) {
      seen.add(t);
      uniqueCells += 1;
    }
  }
  // how often the same cell shape repeats below: a header does not repeat
  let repeatsBelow = 0;
  for (const row of body) {
    for (let i = 0; i < Math.min(row.length, candidate.length); i++) {
      if (row[i]!.trim() === candidate[i]!.trim()) repeatsBelow += 1;
    }
  }
  const n = candidate.length;
  return (textCells / n) * 0.5 + (uniqueCells / n) * 0.5 - (repeatsBelow / (n * Math.max(1, body.length)));
}

export function detectLayout(path: string): LayoutReading {
  // 1. delimiter, by content
  const cands = DELIMITER_CANDIDATES.map((c) => scoreDelimiter(path, c.ch, c.label)).sort((a, b) => b.score - a.score);
  const winner = cands[0]!;
  const runnerUp = cands.length > 1 ? cands[1]! : null;
  const margin = winner.score - (runnerUp ? runnerUp.score : 0);

  // 2. header row, by content, among the first few records
  const head: string[][] = [];
  parseCsv(path, { delimiter: winner.delimiter, quote: '"' }, (fields) => {
    head.push(fields.slice());
    return head.length < 6;
  });
  let bestIdx = 0;
  let bestScore = -Infinity;
  let secondScore = -Infinity;
  for (let i = 0; i < Math.min(head.length, 3); i++) {
    const s = headerScore(head[i]!, head.slice(i + 1));
    if (s > bestScore) {
      secondScore = bestScore;
      bestScore = s;
      bestIdx = i;
    } else if (s > secondScore) {
      secondScore = s;
    }
  }

  // 3. whole-file field-count distribution and encoding, one streaming pass
  const stats = parseCsv(path, { delimiter: winner.delimiter, quote: '"' }, () => {
    /* counting only */
  });

  const note =
    "delimiter=" +
    winner.label +
    " [score " +
    intText(winner.score) +
    " vs " +
    (runnerUp ? runnerUp.label + " " + intText(runnerUp.score) : "none") +
    ", margin " +
    intText(margin) +
    "]; header on record " +
    intText(bestIdx + 1) +
    " [score " +
    intText(Math.round(bestScore * 1000)) +
    "/1000 vs runner-up " +
    intText(Math.round((Number.isFinite(secondScore) ? secondScore : 0) * 1000)) +
    "/1000, margin " +
    intText(Math.round((bestScore - (Number.isFinite(secondScore) ? secondScore : 0)) * 1000)) +
    "/1000]";

  return {
    encoding: { utf8Strict: stats.utf8Strict, byteOrderMark: stats.byteOrderMark },
    delimiter: { winner, runnerUp, margin },
    headerRow: {
      index: bestIdx,
      score: bestScore,
      runnerUpScore: Number.isFinite(secondScore) ? secondScore : 0,
      margin: bestScore - (Number.isFinite(secondScore) ? secondScore : 0),
      names: head[bestIdx] ? head[bestIdx]!.slice() : [],
    },
    fieldCountHistogram: stats.fieldCountHistogram,
    dataRecords: Math.max(0, stats.records - (bestIdx + 1)),
    recordsWithQuotedDelimiter: stats.recordsWithQuotedDelimiter,
    lineTerminators: { lf: stats.lf, crlf: stats.crlf },
    note,
  };
}

/**
 * A NAIVE reading of the same file: split every physical line on the delimiter,
 * ignoring quotes. Used only as a cross-check.
 *
 * R8: the io layer's comparison against the neutral spec shares the quote-aware
 * parser with the run itself, so a fault in that parser would make both readings
 * wrong together and the agreement would be tautological. This second reading
 * shares nothing with it. Where the two histograms differ, quoted delimiters are
 * present and the quote handling is demonstrably doing work -- which is the
 * hazard the spec reports and the mistake the controller's own profiler made.
 */
export function naiveFieldCountHistogram(path: string, delimiter: string): Map<number, number> {
  const hist = new Map<number, number>();
  const decoder = new TextDecoder("utf-8", { fatal: false, ignoreBOM: false });
  let carry = "";
  const countLine = (line: string) => {
    if (line.length === 0) return;
    const n = line.split(delimiter).length;
    hist.set(n, (hist.get(n) ?? 0) + 1);
  };
  streamBytes(path, (b, n) => {
    carry += decoder.decode(b.subarray(0, n), { stream: true });
    for (;;) {
      const ix = carry.indexOf("\n");
      if (ix < 0) break;
      let line = carry.slice(0, ix);
      if (line.endsWith("\r")) line = line.slice(0, line.length - 1);
      countLine(line);
      carry = carry.slice(ix + 1);
    }
  });
  carry += decoder.decode();
  countLine(carry);
  return hist;
}
