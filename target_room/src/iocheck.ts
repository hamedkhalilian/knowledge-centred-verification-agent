// src/iocheck.ts
//
// R7 -- DO NOT LET ONE IMPLEMENTATION CONFIGURE THE OTHER.
//
// The neutral spec's `io_formats` block states facts about the input that the
// SOURCE side observed. This module treats every one of them as a CLAIM TO
// VERIFY. Nothing here is read out of the spec and used as a setting: the io
// layer detects the layout from the file's own content (csv.ts), and this module
// then diffs the two readings and says, for each claim, which reading each side
// holds and whether they agree.
//
// The halting rule is deliberately narrow, and it is the lesson of run 2. R7's
// scope is "the facts the computation depends on". A disagreement about the
// delimiter, the quoting, the encoding or the presence of a field the unit reads
// by name changes what is computed, so it halts. A disagreement about how many
// rows the file has, how many of them carry a quoted comma, or how many values
// of an amount field happen to be missing does NOT change what is computed --
// the unit reads whatever is there -- so it is REPORTED, loudly, and the run
// continues. Run 2 shipped a target that demanded the input's column list equal
// the spec's list and then refused a real file the source reads happily; a
// surplus field is a reported difference, never a halt.

import { intText } from "./canonical.js";
import type { LayoutReading } from "./csv.js";
import { INPUT_COLUMNS } from "./engine.js";

export type ClaimClass = "computation_critical" | "observational";

export interface ClaimResult {
  id: string;
  claim: string;
  klass: ClaimClass;
  specReading: string;
  targetReading: string;
  agreed: boolean;
}

export class IoDisagreement extends Error {
  constructor(public readonly results: ClaimResult[]) {
    super(
      "io layer HALT: the target's own reading of the input disagrees with the neutral spec on " +
        intText(results.length) +
        " computation-critical claim(s). Both readings are named in the run report.",
    );
    this.name = "IoDisagreement";
  }
}

function eq(a: string, b: string): boolean {
  return a === b;
}

/**
 * Structural claims. Checked BEFORE any row is computed, because a disagreement
 * here changes what would be computed.
 */
export function checkStructural(
  layout: LayoutReading,
  headerNames: string[],
  declaredCoercions: string[],
): ClaimResult[] {
  const out: ClaimResult[] = [];

  out.push({
    id: "IO-ENC",
    claim: "the contract table is UTF-8",
    klass: "computation_critical",
    specReading: "UTF-8",
    targetReading: layout.encoding.utf8Strict
      ? "decoded as strict UTF-8" + (layout.encoding.byteOrderMark ? " (with a byte-order mark)" : "")
      : "NOT valid UTF-8",
    agreed: layout.encoding.utf8Strict,
  });

  out.push({
    id: "IO-DELIM",
    claim: "fields are comma-delimited under proper quoting",
    klass: "computation_critical",
    specReading: "comma",
    targetReading: layout.note,
    agreed: eq(layout.delimiter.winner.delimiter, ","),
  });

  const hist = Array.from(layout.fieldCountHistogram.entries()).sort((a, b) => a[0] - b[0]);
  const uniform = hist.length === 1;
  out.push({
    id: "IO-RAGGED",
    claim: "every record carries the same number of fields under proper quoting",
    klass: "computation_critical",
    specReading: "exactly eleven comma-delimited fields on every line under proper quoting",
    targetReading:
      "field-count histogram " +
      hist.map(([k, v]) => intText(k) + "x" + intText(v)).join(", ") +
      (uniform ? " (uniform)" : " (RAGGED)"),
    agreed: uniform,
  });

  const present = INPUT_COLUMNS.filter((c) => headerNames.indexOf(c) >= 0);
  const absent = INPUT_COLUMNS.filter((c) => headerNames.indexOf(c) < 0);
  out.push({
    id: "IO-NAMES",
    claim: "the unit's eleven field names are bound exactly and case-sensitively",
    klass: "computation_critical",
    specReading: INPUT_COLUMNS.join(", "),
    targetReading:
      absent.length === 0
        ? "all eleven bound: " + present.join(", ")
        : "ABSENT: " + absent.join(", ") + "; bound: " + present.join(", "),
    agreed: absent.length === 0,
  });

  out.push({
    id: "IO-BSV",
    claim: "the identifier field BSV is present",
    klass: "computation_critical",
    specReading: "present; the writer stops with a named refusal when it is not",
    targetReading: headerNames.indexOf("BSV") >= 0 ? "present" : "ABSENT",
    agreed: headerNames.indexOf("BSV") >= 0,
  });

  const surplus = headerNames.filter((h) => INPUT_COLUMNS.indexOf(h) < 0);
  out.push({
    id: "IO-SURPLUS",
    claim: "any further field in the table is ignored; the unit selects the eleven it needs by name",
    klass: "observational",
    specReading: "surplus fields are reported, never rejected",
    targetReading:
      surplus.length === 0 ? "no surplus fields" : "surplus fields ignored: " + surplus.join(", "),
    agreed: true,
  });

  const declared = declaredCoercions.slice().sort().join(", ");
  const expected = ["abschlussdatum", "einloesungsdatum"].join(", ");
  out.push({
    id: "IO-COERCE",
    claim: "the harness coerces exactly abschlussdatum and einloesungsdatum to a date type",
    klass: "computation_critical",
    specReading: expected,
    targetReading: "input manifest declares: " + (declared.length ? declared : "(none)"),
    agreed: declared === expected,
  });

  return out;
}

/** Observational claims. Reported after the run; never a halt. */
export interface ObservationalInputs {
  dataRecords: number;
  recordsWithQuotedDelimiter: number;
  tariffDistinct: string[];
  tariffMissing: number;
  tariffMin: number;
  tariffMax: number;
  contractTypeDistinct: string[];
  contractTypeEmpty: number;
  idMin: string;
  idMax: string;
  daBetragMin: number;
  daBetragMax: number;
  daBetragMissing: number;
  daBetragZeroText: number;
  daBetragEmptyText: number;
  bausparMin: number;
  bausparMax: number;
  bausparMissing: number;
  bausparZeroText: number;
  bausparEmptyText: number;
  guthabenMin: number;
  guthabenMax: number;
  guthabenMissing: number;
  dateMinIso: string;
  dateMaxIso: string;
  dateMarkersSeen: string[];
  renderNumber: (v: number) => string;
}

export function checkObservational(o: ObservationalInputs): ClaimResult[] {
  const n = o.renderNumber;
  const res: ClaimResult[] = [];
  const add = (id: string, claim: string, spec: string, target: string) =>
    res.push({ id, claim, klass: "observational", specReading: spec, targetReading: target, agreed: spec === target });

  add("IO-ROWS", "503 data rows and one header row", "503", intText(o.dataRecords));
  add(
    "IO-QUOTED",
    "103 of the 503 data lines carry quoted fields containing commas",
    "103",
    intText(o.recordsWithQuotedDelimiter),
  );
  add(
    "IO-TARIFF-SET",
    "distinct tariff share values in full",
    "0,3000 | 0,3500 | 0,4000 | 0,5000 | 0.3 | 0.35 | 0.4 | 0.5 | NA",
    o.tariffDistinct.slice().sort().join(" | "),
  );
  add("IO-TARIFF-MISSING", "89 of 503 rows carry the missing marker", "89", intText(o.tariffMissing));
  add("IO-TARIFF-RANGE", "tariff values run from 0.3 to 0.5 once read", "0.3 .. 0.5", n(o.tariffMin) + " .. " + n(o.tariffMax));
  add(
    "IO-CTYPE-SET",
    "distinct contract type values in full",
    "(empty) | BS1 | BS2 | BSK | VL7",
    o.contractTypeDistinct.slice().sort().map((s) => (s === "" ? "(empty)" : s)).join(" | "),
  );
  add("IO-CTYPE-EMPTY", "83 of 503 rows carry the empty contract type", "83", intText(o.contractTypeEmpty));
  add("IO-ID-RANGE", "identifiers 800000 to 900023", "800000 .. 900023", o.idMin + " .. " + o.idMax);
  add("IO-DABETRAG", "DaBetrag 0 to 295982.79 with 2 missing", "0 .. 295982.79 with 2 missing",
    n(o.daBetragMin) + " .. " + n(o.daBetragMax) + " with " + intText(o.daBetragMissing) + " missing" +
    " [reconciliation: " + intText(o.daBetragEmptyText) + " empty text + " + intText(o.daBetragZeroText) +
    " text '0' = " + intText(o.daBetragEmptyText + o.daBetragZeroText) +
    "; behaviour step C2 and the constant amount_missing_markers make the text '0' a ZERO, not a missing value]");
  add("IO-BAUSPAR", "bausparsumme_teuro 0 to 50.972 with 3 missing", "0 .. 50.972 with 3 missing",
    n(o.bausparMin) + " .. " + n(o.bausparMax) + " with " + intText(o.bausparMissing) + " missing" +
    " [reconciliation: " + intText(o.bausparEmptyText) + " empty text + " + intText(o.bausparZeroText) +
    " text '0' = " + intText(o.bausparEmptyText + o.bausparZeroText) +
    "; behaviour step C2 and the constant amount_missing_markers make the text '0' a ZERO, not a missing value]");
  add("IO-GUTHABEN", "guthaben 318.53 to 216706.84 with none missing", "318.53 .. 216706.84 with 0 missing",
    n(o.guthabenMin) + " .. " + n(o.guthabenMax) + " with " + intText(o.guthabenMissing) + " missing");
  add("IO-DATES", "parsed dates from 1998-01-04 to 2043-10-15", "1998-01-04 .. 2043-10-15",
    o.dateMinIso + " .. " + o.dateMaxIso);
  add(
    "IO-MARKERS",
    "the missing markers actually present in the date fields are the empty text, 0, 00000000 and NA",
    "(empty) | 0 | 00000000 | NA",
    o.dateMarkersSeen.slice().sort().map((s) => (s === "" ? "(empty)" : s)).join(" | "),
  );
  return res;
}

export function haltOnCriticalDisagreement(results: ClaimResult[]): void {
  const bad = results.filter((r) => r.klass === "computation_critical" && !r.agreed);
  if (bad.length > 0) throw new IoDisagreement(bad);
}
