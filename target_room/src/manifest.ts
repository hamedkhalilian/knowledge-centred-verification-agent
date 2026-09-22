// src/manifest.ts
//
// The input manifest, read as DECLARED DATA (target directive 5).
//
// Two things in it are settings and are applied exactly as declared, never
// inferred: the harness coercions and the valuation date. Controller directive
// 01 is explicit that which columns the harness coerces changes whether the
// abort path fires, so that setting is part of the observation contract; a
// target that guessed it would be guessing about the abort.
//
// Everything else in the manifest -- the column list, the row count, the marker
// list -- is a CLAIM about the file and is verified against the file's content
// by iocheck.ts (R7). It is never adopted as configuration.

import * as fs from "node:fs";
import * as path from "node:path";

export interface Manifest {
  file: string;
  valuationDate: string | null;
  toDateClass: string[];
  leftAsRaw: string[];
  claimedColumns: string[] | null;
  claimedRowCount: number | null;
  claimedEmptyMarkers: string[] | null;
  raw: unknown;
}

/**
 * Find the manifest beside the input table, by content of the directory.
 * A missing or ambiguous manifest is named and halts: the coercions may not be
 * inferred, so proceeding without them would be a silent guess (R16).
 */
export function findManifest(inputPath: string, override: string | null): string {
  if (override !== null) {
    if (!fs.existsSync(override)) {
      throw new Error("manifest not found: " + override + " (no such file -- check for a typo, a moved file, or a stray quote)");
    }
    return override;
  }
  const dir = path.dirname(path.resolve(inputPath));
  const hits = fs.readdirSync(dir).filter((f) => f.endsWith("manifest.json")).sort();
  if (hits.length === 0) {
    throw new Error(
      "no input manifest found beside " + inputPath + " (looked for *manifest.json in " + dir +
      "). The harness coercions are a declared setting and may not be inferred; supply --manifest <path>.",
    );
  }
  if (hits.length > 1) {
    throw new Error(
      "more than one candidate manifest beside " + inputPath + ": " + hits.join(", ") +
      ". Refusing to choose; supply --manifest <path>.",
    );
  }
  return path.join(dir, hits[0]!);
}

export function readManifest(manifestPath: string): Manifest {
  const text = fs.readFileSync(manifestPath, "utf8");
  const raw = JSON.parse(text) as Record<string, unknown>;
  const hc = (raw["harness_coercions"] ?? {}) as Record<string, unknown>;
  const toDate = Array.isArray(hc["to_date_class"]) ? (hc["to_date_class"] as string[]) : [];
  const leftRaw = Array.isArray(hc["left_as_raw_yyyymmdd"]) ? (hc["left_as_raw_yyyymmdd"] as string[]) : [];
  return {
    file: manifestPath,
    valuationDate: typeof raw["valuation_date"] === "string" ? (raw["valuation_date"] as string) : null,
    toDateClass: toDate.slice(),
    leftAsRaw: leftRaw.slice(),
    claimedColumns: Array.isArray(raw["columns"]) ? (raw["columns"] as string[]).slice() : null,
    claimedRowCount: typeof raw["row_count"] === "number" ? (raw["row_count"] as number) : null,
    claimedEmptyMarkers: Array.isArray(raw["empty_markers_used"])
      ? (raw["empty_markers_used"] as string[]).slice()
      : null,
    raw,
  };
}
