// src/pipeline.ts
//
// One observation of the unit over one contract table: read the layout by
// content, diff it against the neutral spec's claims (R7), apply the declared
// harness coercions (controller directive 01), compute every row, evaluate the
// preconditions, and build the three checkpoint objects.
//
// Everything that writes a file lives in index.ts. This module is pure enough to
// be run twice -- once on the real staged input and once on each of the
// self-test fixtures -- which is what makes the R18 good-input control run
// possible at all.

import * as path from "node:path";
import { detectLayout, naiveFieldCountHistogram, parseCsv, type LayoutReading } from "./csv.js";
import { findManifest, readManifest, type Manifest } from "./manifest.js";
import { checkStructural, checkObservational, haltOnCriticalDisagreement, type ClaimResult } from "./iocheck.js";
import { coerceColumns, runTable, DATE_FIELDS, type Aggregates, type CoercionOutcome } from "./table.js";
import { evaluatePreconditions, type PreconditionResult } from "./preconditions.js";
import { buildCheckpointObject, type CheckpointObject, type OrderKey } from "./checkpoint.js";
import { documentLines, documentText } from "./script.js";
import { makeStore, pushNum, pushStr, type ObjectStore } from "./store.js";
import { DEFAULT_CONFIG, type EngineConfig } from "./engine.js";
import { isDateMissingMarker, parseStandardUnambiguous, renderIsoDate } from "./dates.js";
import { Journal } from "./logging.js";
import { intText, scriptNumber } from "./canonical.js";

export interface PipelineOptions {
  inputPath: string;
  manifestPath: string | null;
  valuationDateArg: string | null;
  journal: Journal;
  /** false only for the self-test fixtures, whose observational claims are about a different file */
  compareObservational: boolean;
  config?: EngineConfig;
}

export interface PipelineResult {
  inputPath: string;
  manifest: Manifest;
  layout: LayoutReading;
  headerNames: string[];
  naiveHistogram: Map<number, number>;
  claims: ClaimResult[];
  coercions: Map<string, CoercionOutcome>;
  aggregates: Aggregates;
  book: ObjectStore;
  exportRows: ObjectStore;
  jsDocument: ObjectStore;
  documentTextValue: string;
  preconditions: PreconditionResult[];
  checkpointObjects: CheckpointObject[];
  valuationDay: number;
  valuationDateSource: string;
  dateMarkersSeen: string[];
}

const BOOK_ORDER: OrderKey[] = [
  { column: "id", direction: "asc" },
  { column: "row_index", direction: "asc" },
];
const DOC_ORDER: OrderKey[] = [{ column: "line_no", direction: "asc" }];

export function runPipeline(opts: PipelineOptions): PipelineResult {
  const journal = opts.journal;
  const cfg = opts.config ?? DEFAULT_CONFIG;

  // --- the input manifest, read as declared data -----------------------------
  const manifestPath = findManifest(opts.inputPath, opts.manifestPath);
  const manifest = readManifest(manifestPath);

  // --- the valuation date ----------------------------------------------------
  let valuationText: string;
  let valuationSource: string;
  if (opts.valuationDateArg !== null) {
    valuationText = opts.valuationDateArg;
    valuationSource = "second command-line argument";
  } else if (manifest.valuationDate !== null) {
    valuationText = manifest.valuationDate;
    valuationSource = "input manifest " + path.basename(manifestPath) + " field valuation_date";
  } else {
    throw new Error(
      "no valuation date: none was given as the second argument and the input manifest " +
        manifestPath + " carries no valuation_date field. Refusing to substitute the unit's own " +
        "load-time default, which is a default INSIDE the unit and not an input (P-12).",
    );
  }
  const valuationDay = parseStandardUnambiguous(valuationText.trim());
  if (valuationDay === null) {
    throw new Error("valuation date " + JSON.stringify(valuationText) + " is not a calendar date in year-month-day order");
  }

  // --- layout, detected from the file's own content (GR-07, R5) --------------
  const layout = detectLayout(opts.inputPath);
  const headerNames = layout.headerRow.names.slice();
  const naiveHistogram = naiveFieldCountHistogram(opts.inputPath, layout.delimiter.winner.delimiter);

  const fieldIndex = new Map<string, number>();
  for (let i = 0; i < headerNames.length; i++) {
    if (!fieldIndex.has(headerNames[i]!)) fieldIndex.set(headerNames[i]!, i);
    else {
      journal.note({
        kind: "ignored", where: "header", what: "duplicate header name " + JSON.stringify(headerNames[i]!),
        why: "a second field with the same name; the unit selects by name and binds the first, and the later one is ignored",
        rowIndex: null, column: headerNames[i]!,
      });
    }
  }

  // --- R7: diff the two readings; halt only where the computation depends on it
  const claims = checkStructural(layout, headerNames, manifest.toDateClass);
  haltOnCriticalDisagreement(claims);

  // --- harness coercions, PASS A --------------------------------------------
  const coercions = coerceColumns(
    opts.inputPath, layout.delimiter.winner.delimiter, layout.headerRow.index,
    fieldIndex, manifest.toDateClass, journal,
  );
  for (const c of manifest.leftAsRaw) {
    journal.note({
      kind: "info", where: "harness coercion",
      what: "column '" + c + "' left as raw year-month-day digits",
      why: "declared in the input manifest; the unit parses it itself, so every hyphenated unreadable value in it aborts (controller directive 01, path 1)",
      rowIndex: null, column: c,
    });
  }

  // --- PASS B ----------------------------------------------------------------
  const run = runTable(
    opts.inputPath, layout.delimiter.winner.delimiter, layout.headerRow.index, fieldIndex,
    coercions, valuationDay, cfg, journal, layout.dataRecords,
  );

  // --- the browser data document (behaviour step C24) ------------------------
  if (run.aggregates.rowsRead === 0) {
    throw new Error("the browser-data writer stops: the contract table is empty of content");
  }
  if (!fieldIndex.has("BSV")) {
    throw new Error("the browser-data writer stops: the contract table has no BSV field");
  }
  const lines = documentLines(run.entries, run.aggregates.rowsRead, valuationDay);
  const docText = documentText(lines);
  const jsDocument = makeStore("customers_js_document", [["line_no", "num"], ["line_text", "str"]]);
  for (let i = 0; i < lines.length; i++) {
    pushNum(jsDocument, 0, i + 1);
    pushStr(jsDocument, 1, lines[i]!);
  }

  // --- which date missing markers this input actually exercises --------------
  const markersSeen = collectDateMarkers(
    opts.inputPath, layout.delimiter.winner.delimiter, layout.headerRow.index, fieldIndex,
  );

  // --- preconditions ---------------------------------------------------------
  const preconditions = evaluatePreconditions({
    agg: run.aggregates,
    headerNames,
    valuationDay,
    valuationDateSource: valuationSource,
    coercedColumns: manifest.toDateClass,
    dateMarkerSet: markersSeen,
  });

  // --- observational claims (reported, never a halt) -------------------------
  if (opts.compareObservational) {
    const a = run.aggregates;
    const da = a.amountStats.get("DaBetrag")!;
    const bs = a.amountStats.get("bausparsumme_teuro")!;
    const gu = a.amountStats.get("guthaben")!;
    let dMin = NaN;
    let dMax = NaN;
    for (const st of a.dateStats.values()) {
      if (st.parsedCount === 0) continue;
      if (Number.isNaN(dMin) || st.minDay < dMin) dMin = st.minDay;
      if (Number.isNaN(dMax) || st.maxDay > dMax) dMax = st.maxDay;
    }
    const ids = idRange(opts.inputPath, layout.delimiter.winner.delimiter, layout.headerRow.index, fieldIndex);
    claims.push(
      ...checkObservational({
        dataRecords: a.rowsRead,
        recordsWithQuotedDelimiter: layout.recordsWithQuotedDelimiter,
        tariffDistinct: Array.from(a.amountStats.get("tariff_amount")!.distinct),
        tariffMissing: a.amountStats.get("tariff_amount")!.missing,
        tariffMin: a.tariff.min,
        tariffMax: a.tariff.max,
        contractTypeDistinct: Array.from(a.contractTypeTally.keys()),
        contractTypeEmpty: a.contractTypeTally.get("") ?? 0,
        idMin: ids.min,
        idMax: ids.max,
        daBetragMin: da.min, daBetragMax: da.max, daBetragMissing: da.missing,
        daBetragZeroText: da.zeroText, daBetragEmptyText: da.emptyText,
        bausparMin: bs.min, bausparMax: bs.max, bausparMissing: bs.missing,
        bausparZeroText: bs.zeroText, bausparEmptyText: bs.emptyText,
        guthabenMin: gu.min, guthabenMax: gu.max, guthabenMissing: gu.missing,
        dateMinIso: Number.isNaN(dMin) ? "none" : renderIsoDate(dMin),
        dateMaxIso: Number.isNaN(dMax) ? "none" : renderIsoDate(dMax),
        dateMarkersSeen: markersSeen,
        renderNumber: scriptNumber,
      }),
    );
    claims.push({
      id: "IO-QUOTE-HAZARD",
      claim: "a reader that splits on the delimiter instead of parsing quoted fields mis-assigns fields silently",
      klass: "observational",
      specReading: "103 lines would show 14 or 15 fields under a naive split",
      targetReading:
        "quote-aware histogram " + histText(layout.fieldCountHistogram) +
        " vs naive-split histogram " + histText(naiveHistogram) +
        " -- two structurally different readings of the same file (R8)",
      agreed: true,
    });
  }

  const checkpointObjects = [
    buildCheckpointObject(run.book, BOOK_ORDER),
    buildCheckpointObject(run.exportRows, BOOK_ORDER),
    buildCheckpointObject(jsDocument, DOC_ORDER),
  ];

  return {
    inputPath: opts.inputPath,
    manifest,
    layout,
    headerNames,
    naiveHistogram,
    claims,
    coercions,
    aggregates: run.aggregates,
    book: run.book,
    exportRows: run.exportRows,
    jsDocument,
    documentTextValue: docText,
    preconditions,
    checkpointObjects,
    valuationDay,
    valuationDateSource: valuationSource,
    dateMarkersSeen: markersSeen,
  };
}

function histText(h: Map<number, number>): string {
  return Array.from(h.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([k, v]) => intText(k) + "x" + intText(v))
    .join(", ");
}

function collectDateMarkers(
  inputPath: string, delimiter: string, headerIndex: number, fieldIndex: Map<string, number>,
): string[] {
  const seen = new Set<string>();
  parseCsv(inputPath, { delimiter, quote: '"' }, (fields, recordIndex) => {
    if (recordIndex <= headerIndex) return true;
    for (const f of DATE_FIELDS) {
      const ix = fieldIndex.get(f);
      if (ix === undefined) continue;
      const t = (fields[ix] ?? "").trim();
      if (isDateMissingMarker(t)) seen.add(t);
    }
    return true;
  });
  return Array.from(seen).sort();
}

function idRange(
  inputPath: string, delimiter: string, headerIndex: number, fieldIndex: Map<string, number>,
): { min: string; max: string } {
  let min: string | null = null;
  let max: string | null = null;
  const ix = fieldIndex.get("BSV");
  if (ix === undefined) return { min: "(absent)", max: "(absent)" };
  parseCsv(inputPath, { delimiter, quote: '"' }, (fields, recordIndex) => {
    if (recordIndex <= headerIndex) return true;
    const v = fields[ix] ?? "";
    if (min === null || v < min) min = v;
    if (max === null || v > max) max = v;
    return true;
  });
  return { min: min ?? "(none)", max: max ?? "(none)" };
}
