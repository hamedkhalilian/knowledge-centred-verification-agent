// src/selftest.ts
//
// GR-13 / target directive 16 / R8 / R18.
//
// Three kinds of check, and they are not interchangeable:
//
//  A. CONTRACT VECTORS. The canonicalisation contract requires its reference
//     vectors to be self-tested at startup and the emitter to abort on
//     mismatch; the neutral spec requires the same of the sixteen measured
//     rounding vectors. These are memorised constants, which GR-13 warns
//     against on its own -- so they are paired with (B).
//
//  B. INVERSION AND PROPERTY CHECKS, which survive a data change because they
//     test a mathematical property rather than a remembered number: rounding is
//     idempotent and bracketed; the canonical rendering is idempotent under
//     re-parse; the calendar conversion round-trips; a digest is stable under a
//     re-run and sensitive to a single changed cell; the quote-aware parser
//     reproduces a file it did not write.
//
//  C. THE GOOD-INPUT CONTROL RUN (R18). Every precondition is run end to end
//     over a fixture known to be GOOD and over a fixture known to be BAD, and
//     the separation between the two is reported. A check that has only ever
//     been tested on the defect it was written for is not calibrated. This run
//     has already lost time twice to checks that passed vacuously or cried wolf
//     on sound input.
//
// Blind spots (R8) are enumerated at the end of this file and printed with the
// results, because a suite whose blind spots are not enumerated is not a suite.

import * as fs from "node:fs";
import * as path from "node:path";
import {
  canonicalNumber, canonicalString, canonicalDate, canonicalLogical, scriptNumber, intText,
} from "./canonical.js";
import { roundRecord } from "./round.js";
import {
  daysFromCivil, civilFromDays, parseEightDigits, parseStandardUnambiguous, readDateText,
  DateParseAbort, yearLabel,
} from "./dates.js";
import { readAmountText } from "./numbers.js";
import { parseCsv } from "./csv.js";
import { makeStore, pushNum, pushStr } from "./store.js";
import { buildCheckpointObject, canonicalOrder } from "./checkpoint.js";
import { runPipeline } from "./pipeline.js";
import { Journal } from "./logging.js";
import type { PreconditionResult } from "./preconditions.js";

export interface CheckResult {
  group: string;
  name: string;
  ok: boolean;
  detail: string;
}

export interface SelfTestReport {
  results: CheckResult[];
  passed: number;
  failed: number;
  blindSpots: string[];
  separation: string[];
}

function chk(results: CheckResult[], group: string, name: string, ok: boolean, detail: string): void {
  results.push({ group, name, ok, detail });
}

// --- A. contract vectors -----------------------------------------------------

const CANONICAL_VECTORS: Array<[string, number | null, string]> = [
  ["1", 1, "1.00000000e+00"],
  ["-0.0", -0, "0.00000000e+00"],
  ["2^-13 (decimal tie at digit 9)", Math.pow(2, -13), "1.22070312e-04"],
  ["1/3", 1 / 3, "3.33333333e-01"],
  ["123456789.5", 123456789.5, "1.23456790e+08"],
  ["-2.5e-10", -2.5e-10, "-2.50000000e-10"],
  ["NaN", NaN, "NA"],
  ["NA (null)", null, "NA"],
];

const ROUND_VECTORS: Array<[string, number, number, number]> = [
  ["0.1235 at 3 places", 0.1235, 3, 0.124],
  ["0.0055 at 3 places", 0.0055, 3, 0.005],
  ["0.0095 at 3 places", 0.0095, 3, 0.01],
  ["0.0085 at 3 places", 0.0085, 3, 0.009],
  ["0.0005 at 3 places", 0.0005, 3, 0],
  ["0.0625 at 3 places", 0.0625, 3, 0.062],
  ["0.1875 at 3 places", 0.1875, 3, 0.188],
  ["0.4445 at 3 places", 0.4445, 3, 0.444],
  ["-0.0055 at 3 places", -0.0055, 3, -0.005],
  ["0.12345 at 4 places", 0.12345, 4, 0.1235],
  ["0.5 at 0 places", 0.5, 0, 0],
  ["1.5 at 0 places", 1.5, 0, 2],
  ["2.5 at 0 places", 2.5, 0, 2],
  ["14500.5 at 0 places", 14500.5, 0, 14500],
  ["14501.5 at 0 places", 14501.5, 0, 14502],
  ["123456789.5 at 0 places", 123456789.5, 0, 123456790],
];

/** Behaviour step C22's own worked examples. */
const SCRIPT_VECTORS: Array<[string, number, string]> = [
  ["0.4", 0.4, "0.4"],
  ["14500", 14500, "14500"],
  ["one ten-millionth", 1e-7, "0"],
  ["negative zero", -0, "-0"],
  ["1/3", 1 / 3, "0.333333"],
  ["2.5e-7 (half-even at the sixth place, to even)", 2.5e-7, "0"],
  ["7.5e-7 (half-even at the sixth place, to even)", 7.5e-7, "0.000001"],
];

// --- fixtures for the good-input control run --------------------------------

const FIXTURE_HEADER =
  "BSV,abschlussdatum,einloesungsdatum,erstmalige_zuteilungsanwartschaft,Tilgungsbeginn,Vertragsende,DaBetrag,bausparsumme_teuro,guthaben,tariff_amount,contract_type";

const GOOD_ROWS = [
  "700001,2001-03-01,2001-04-01,20110401,20110601,20220601,30000,30,12000,0.4,BS1",
  "700002,2007-05-01,2007-06-01,20200101,20200301,20310301,20000,20,11230,0.4,BS1",
  "700003,2019-01-01,2019-02-01,20290201,,,40000,40,4000,0.4,BS2",
  "700004,2015-06-15,2015-07-15,20250715,,,25000,25,18000,0.35,BSK",
  '700005,2010-02-02,2010-03-02,20200302,,,"36.263,14","36,263","20.000,00",0.5,VL7',
  "700006,2012-09-09,2012-10-09,20221009,20230101,20330101,15000,15,9000,0.3,BS2",
];

// Known-bad, and deliberately WITHOUT a hyphenated unreadable date: that value
// would abort the run rather than produce a precondition verdict, and the abort
// path has its own probe (controller directive 01, Rule E).
const BAD_ROWS = [
  "700001,2001-03-01,2001-04-01,20110401,20110601,20220601,30000,30000,12000,40,BS1",
  "700001,2007-05-01,2007-06-01,2011/04/01,,,20000,20000,-11230,40,BS1",
  '700003,2019-01-01,2019-02-01,20290201,,,"1,2,3",40000,4000,40,BS2',
];
const BAD_HEADER = FIXTURE_HEADER + ",guthaben_alt";
const BAD_SUFFIX = ",99";

const FIXTURE_MANIFEST = JSON.stringify(
  {
    provenance: "selftest_fixture",
    valuation_date: "2026-03-31",
    harness_coercions: {
      to_date_class: ["abschlussdatum", "einloesungsdatum"],
      left_as_raw_yyyymmdd: ["erstmalige_zuteilungsanwartschaft", "Tilgungsbeginn", "Vertragsende"],
    },
  },
  null,
  2,
);

function writeFixture(dir: string, name: string, header: string, rows: string[]): string {
  fs.mkdirSync(dir, { recursive: true });
  const p = path.join(dir, name);
  fs.writeFileSync(p, header + "\n" + rows.join("\n") + "\n", "utf8");
  fs.writeFileSync(path.join(dir, "fixture_manifest.json"), FIXTURE_MANIFEST, "utf8");
  return p;
}

// ---------------------------------------------------------------------------

export function runSelfTests(workDir: string): SelfTestReport {
  const results: CheckResult[] = [];

  // ---- A. canonicalisation contract reference vectors
  for (const [name, v, want] of CANONICAL_VECTORS) {
    const got = canonicalNumber(v);
    chk(results, "canonical reference vectors", name, got === want, "got " + got + ", want " + want);
  }
  chk(results, "canonical reference vectors", "logical true/false/NA",
    canonicalLogical(true) === "true" && canonicalLogical(false) === "false" && canonicalLogical(null) === "NA",
    "true/false/NA");
  chk(results, "canonical reference vectors", "date renders as epoch days; missing as NA",
    canonicalDate(daysFromCivil(1970, 1, 2)) === "1" && canonicalDate(daysFromCivil(1969, 12, 31)) === "-1" &&
    canonicalDate(NaN) === "NA",
    "1970-01-02 -> 1, 1969-12-31 -> -1, missing -> NA");
  chk(results, "canonical reference vectors", "string escapes are exactly three",
    canonicalString("a\\b\nc\rd\te\"f") === "a\\\\b\\nc\\rd\te\"f",
    "backslash, LF and CR escaped; tab and quote left alone; got " + JSON.stringify(canonicalString("a\\b\nc\rd\te\"f")));
  chk(results, "canonical reference vectors", "infinities",
    canonicalNumber(Infinity) === "INF" && canonicalNumber(-Infinity) === "-INF", "INF / -INF");

  // ---- A. the sixteen measured rounding vectors of behaviour step C20
  for (const [name, x, d, want] of ROUND_VECTORS) {
    const got = roundRecord(x, d);
    const ok = got === want && (want !== 0 || Object.is(got, want));
    chk(results, "C20 rounding reference vectors", name, ok,
      "got " + scriptNumber(got) + ", want " + scriptNumber(want));
  }
  chk(results, "C20 rounding reference vectors", "the rule is NOT multiply-round-divide",
    roundRecord(0.0055, 3) !== naiveMultiplyRoundDivide(0.0055, 3) ||
    roundRecord(0.0085, 3) !== naiveMultiplyRoundDivide(0.0085, 3),
    "0.0055 -> " + scriptNumber(roundRecord(0.0055, 3)) + " (naive " + scriptNumber(naiveMultiplyRoundDivide(0.0055, 3)) +
    "), 0.0085 -> " + scriptNumber(roundRecord(0.0085, 3)) + " (naive " + scriptNumber(naiveMultiplyRoundDivide(0.0085, 3)) + ")");
  chk(results, "C20 rounding reference vectors", "the unit's three day constants fall out of the rule",
    roundRecord(3652.5, 0) === 3652 && roundRecord(4017.75, 0) === 4018 && roundRecord(2556.75, 0) === 2557,
    "10x365.25 -> " + scriptNumber(roundRecord(3652.5, 0)) + " (must be 3652, the EVEN neighbour), " +
    "11x365.25 -> " + scriptNumber(roundRecord(4017.75, 0)) + ", 7x365.25 -> " + scriptNumber(roundRecord(2556.75, 0)));
  chk(results, "C20 rounding reference vectors", "a negative value rounding to zero yields NEGATIVE zero",
    Object.is(roundRecord(-0.3, 0), -0), "round(-0.3, 0) is " + (Object.is(roundRecord(-0.3, 0), -0) ? "-0" : "0"));

  // ---- A. behaviour step C22 rendering
  for (const [name, x, want] of SCRIPT_VECTORS) {
    const got = scriptNumber(x);
    chk(results, "C22 script rendering", name, got === want, "got " + got + ", want " + want);
  }
  chk(results, "C22 script rendering", "C22 and C20 are different rules",
    scriptNumber(roundRecord(0.0055, 3)) !== scriptNumber(0.0055),
    "C20 at 3 places gives " + scriptNumber(roundRecord(0.0055, 3)) + "; C22 renders the raw value as " + scriptNumber(0.0055));

  // ---- B. property / inversion checks
  {
    let ok = true;
    let detail = "";
    for (let i = 0; i < 20000; i++) {
      const x = (Math.sin(i * 12.9898) * 43758.5453) % 1000;
      const d = i % 5;
      const r = roundRecord(x, d);
      if (roundRecord(r, d) !== r) { ok = false; detail = "not idempotent at " + scriptNumber(x); break; }
      if (Math.abs(r - x) > 0.5 * Math.pow(10, -d) + 1e-9) { ok = false; detail = "outside the half-ulp bracket at " + scriptNumber(x); break; }
    }
    chk(results, "inversion / property", "C20 rounding is idempotent and bracketed by half a place", ok,
      ok ? "20000 pseudo-random values across 0..5 places" : detail);
  }
  {
    let ok = true;
    let detail = "";
    for (let i = 0; i < 20000; i++) {
      const x = (Math.sin(i * 7.7231) * 9871.13) % 1e6;
      const t = canonicalNumber(x);
      if (canonicalNumber(Number(t)) !== t) { ok = false; detail = "not idempotent under re-parse at " + t; break; }
    }
    chk(results, "inversion / property", "canonical rendering is idempotent under re-parse", ok,
      ok ? "20000 pseudo-random values; render -> parse -> render is a fixed point" : detail);
  }
  {
    let ok = true;
    let detail = "";
    for (let day = -30000; day <= 60000; day += 7) {
      const c = civilFromDays(day);
      if (daysFromCivil(c.y, c.m, c.d) !== day) { ok = false; detail = "round trip failed at epoch day " + intText(day); break; }
    }
    chk(results, "inversion / property", "calendar conversion round-trips", ok,
      ok ? "epoch days -30000..60000 step 7 (1887..2134)" : detail);
  }
  {
    // digest stability and sensitivity: a digest that never changes is not a digest
    const a = makeStore("t", [["i", "num"], ["s", "str"]]);
    const b = makeStore("t", [["i", "num"], ["s", "str"]]);
    for (let i = 0; i < 50; i++) {
      pushNum(a, 0, i); pushStr(a, 1, "v" + intText(i));
      pushNum(b, 0, i); pushStr(b, 1, "v" + intText(i));
    }
    const order = [{ column: "i", direction: "asc" as const }];
    const da = buildCheckpointObject(a, order).digest.value;
    const db = buildCheckpointObject(b, order).digest.value;
    b.columns[1]!.str![17] = "changed";
    const dc = buildCheckpointObject(b, order).digest.value;
    chk(results, "inversion / property", "object digest is stable across builds and sensitive to one cell",
      da === db && da !== dc, "identical stores agree; one changed cell in 100 changes the digest");
  }
  {
    const s = makeStore("t", [["k", "str"], ["i", "num"]]);
    pushStr(s, 0, "b"); pushNum(s, 1, 1);
    pushStr(s, 0, null); pushNum(s, 1, 2);
    pushStr(s, 0, "a"); pushNum(s, 1, 3);
    const asc = canonicalOrder(s, [{ column: "k", direction: "asc" }]);
    const desc = canonicalOrder(s, [{ column: "k", direction: "desc" }]);
    chk(results, "inversion / property", "NA sorts last regardless of direction",
      asc[2] === 1 && desc[2] === 1, "ascending and descending both put the missing key last");
  }
  {
    const p = path.join(workDir, "csv_probe.csv");
    fs.mkdirSync(workDir, { recursive: true });
    const content = 'a,b,c\r\n1,"x,y",3\r\n4,"he said ""hi""",6\n7,"multi\nline",9\n';
    fs.writeFileSync(p, content, "utf8");
    const rows: string[][] = [];
    parseCsv(p, { delimiter: ",", quote: '"' }, (f) => { rows.push(f.slice()); return true; });
    const ok =
      rows.length === 4 &&
      rows[1]![1] === "x,y" &&
      rows[2]![1] === 'he said "hi"' &&
      rows[3]![1] === "multi\nline" &&
      rows.every((r) => r.length === 3);
    chk(results, "inversion / property", "quote-aware parser: embedded delimiter, doubled quote, embedded newline, CRLF", ok,
      ok ? "4 records, 3 fields each" : "got " + JSON.stringify(rows));
  }
  {
    // the date rules, against the behaviours the spec measured
    const cases: Array<[string, string, string]> = [
      ["20110401", "2011-04-01", "eight digits"],
      ["20110401.0", "2011-04-01", "text after a complete match is ignored"],
      ["2013112", "2013-11-02", "fewer than eight digits, read greedily, NOT rejected"],
      ["20131345", "MISSING", "month 13 day 45, digit branch, silently missing"],
      ["2011/04/01", "MISSING", "no hyphen, so the digit branch, and it fails -- NOT read as a date"],
      ["abcdefgh", "MISSING", "no hyphen, unreadable, silently missing"],
      ["000000", "MISSING", "six zeros: not a marker, missing by failing the read (FND-11)"],
      ["", "MISSING", "marker"],
      ["00000000", "MISSING", "marker"],
      ["<NA>", "MISSING", "marker the unit's comment does not list (FND-11)"],
      ["00", "MISSING", "marker the unit's comment does not list (FND-11)"],
      ["0000", "MISSING", "marker the unit's comment does not list (FND-11)"],
    ];
    for (const [input, want, why] of cases) {
      let got: string;
      try {
        const o = readDateText(input, "selftest", 1);
        got = Number.isNaN(o.day) ? "MISSING" : isoOf(o.day);
      } catch (e) {
        got = e instanceof DateParseAbort ? "ABORT" : "THROW";
      }
      chk(results, "C1 date reading", JSON.stringify(input) + " -> " + want, got === want, why + "; got " + got);
    }
    for (const bad of ["2013-13-45", "not-a-date", "2013-02-30"]) {
      let got = "no-abort";
      try { readDateText(bad, "selftest", 1); } catch (e) { if (e instanceof DateParseAbort) got = "ABORT"; }
      chk(results, "C1 date reading", JSON.stringify(bad) + " ABORTS (FND-06)", got === "ABORT", "got " + got);
    }
    chk(results, "C1 date reading", "a two-digit year in the hyphen branch is year eleven, not 2011",
      parseStandardUnambiguous("11-04-01") === daysFromCivil(11, 4, 1),
      "11-04-01 reads as year 11 (the signature P-04 looks for)");
    chk(results, "C1 date reading", "the digit scanner does not backtrack",
      parseEightDigits("2011/04/01") === null,
      "a backtracking regular expression would read this as year 20, month 1, day 1");
    chk(results, "C18 year labels", "estimated allocation carries a tilde only via C18, and a missing date is an empty text",
      yearLabel(NaN) === "" && yearLabel(daysFromCivil(2029, 5, 1)) === "2029", "");
  }
  {
    const cases: Array<[string, string]> = [
      ["36263,14", "36263.14"],
      ["36.263,14", "36263.14"],
      ["1.234.567,89", "1234567.89"],
      ["36.263", "36.263"],
      ["1,2,3", "MISSING"],
      ["", "MISSING"],
      ["NA", "MISSING"],
      ["<NA>", "MISSING"],
      ["n/a", "MISSING"],
      ["-", "MISSING"],
      ["0", "0"],
    ];
    for (const [input, want] of cases) {
      const o = readAmountText(input);
      const got = Number.isNaN(o.value) ? "MISSING" : scriptNumber(o.value);
      chk(results, "C2 number reading", JSON.stringify(input) + " -> " + want, got === want, "got " + got);
    }
    chk(results, "C2 number reading", "FND-01 is reproduced, not repaired",
      readAmountText("36.263").value === 36.263,
      "a thousands dot without a decimal comma reads a thousand times too small, exactly as the source does");
  }

  // ---- C. the good-input control run (R18)
  const separation: string[] = [];
  const goodDir = path.join(workDir, "good");
  const badDir = path.join(workDir, "bad");
  const goodPath = writeFixture(goodDir, "good.csv", FIXTURE_HEADER, GOOD_ROWS);
  const badPath = writeFixture(badDir, "bad.csv", BAD_HEADER, BAD_ROWS.map((r) => r + BAD_SUFFIX));

  let good: PreconditionResult[] = [];
  let bad: PreconditionResult[] = [];
  let ranBoth = true;
  try {
    good = runPipeline({
      inputPath: goodPath, manifestPath: path.join(goodDir, "fixture_manifest.json"),
      valuationDateArg: "2026-03-31", journal: new Journal(), compareObservational: false,
    }).preconditions;
  } catch (e) {
    ranBoth = false;
    chk(results, "R18 good-input control run", "the known-good fixture runs at all", false, String(e));
  }
  try {
    bad = runPipeline({
      inputPath: badPath, manifestPath: path.join(badDir, "fixture_manifest.json"),
      valuationDateArg: "2026-03-31", journal: new Journal(), compareObservational: false,
    }).preconditions;
  } catch (e) {
    ranBoth = false;
    chk(results, "R18 good-input control run", "the known-bad fixture runs at all", false, String(e));
  }

  if (ranBoth) {
    const gmap = new Map(good.map((r) => [r.id, r]));
    const bmap = new Map(bad.map((r) => [r.id, r]));
    // No check may cry wolf on sound input.
    const criedWolf = good.filter((r) => r.status === "FAIL" || r.status === "FLAGGED");
    chk(results, "R18 good-input control run", "no check reports FAIL or FLAGGED on known-good input",
      criedWolf.length === 0,
      criedWolf.length === 0
        ? intText(good.length) + " checks, all PASS or NOT_EXERCISED"
        : "cried wolf: " + criedWolf.map((r) => r.id + "=" + r.status + " (" + r.evidence + ")").join(" | "));

    // Every check that CAN fail must be shown to fail on input that breaches it.
    const mustFire: Array<[string, Status2]> = [
      ["P-03", "FAIL"], ["P-05", "FAIL"], ["P-06", "FLAGGED"], ["P-07", "FLAGGED"],
      ["P-10", "FLAGGED"], ["P-11", "FLAGGED"], ["P-13", "FLAGGED"],
      ["FND-02", "FAIL"], ["FND-04", "FLAGGED"], ["FND-06", "FLAGGED"], ["FND-12", "FLAGGED"],
    ];
    for (const [id, want] of mustFire) {
      const g = gmap.get(id);
      const b = bmap.get(id);
      const ok = !!g && !!b && g.status === "PASS" && b.status === want;
      chk(results, "R18 good-input control run", id + " separates good from bad", ok,
        "good=" + (g ? g.status : "?") + " bad=" + (b ? b.status : "?") + " (want PASS / " + want + ")");
      separation.push(id + ": good=" + (g ? g.status : "?") + ", bad=" + (b ? b.status : "?") + " -- " + (b ? b.evidence : ""));
    }
    // FAIL and FLAGGED stay distinct (target directive 14).
    const sevOk = bad.every((r) => (r.severity === "FLAGGED" ? r.status !== "FAIL" : true));
    chk(results, "R18 good-input control run", "a FLAGGED check never reports FAIL", sevOk,
      "severity and status are kept distinct");
    // A check that could not be exercised says so rather than passing vacuously.
    const vac = good.filter((r) => r.status === "NOT_EXERCISED").map((r) => r.id);
    chk(results, "R18 good-input control run", "unexercised checks say NOT_EXERCISED rather than PASS", true,
      vac.length ? "not exercised on the good fixture: " + vac.join(", ") : "every check was exercised");
  }

  const blindSpots = [
    "The canonicalisation and C20 vectors are constants transcribed from the contract and the spec. A transcription error in the spec itself would be invisible to them. Covered structurally by the idempotence and half-place-bracket properties, which share no constant with the vectors.",
    "The C1 date cases are the behaviours the spec measured on the source. They share the 4/2/2 greedy, non-backtracking scanner assumption with the code under test. Covered by the calendar round-trip, which is independent of the scanner, and by the explicit non-backtracking case 2011/04/01.",
    "canonicalNumber, the digests and roundRecord all rest on exactOf. A fault there would corrupt all three together and every check above would still agree. Partly covered by the render/re-parse fixed point, which crosses into the runtime's own correctly-rounded decimal conversion.",
    "The io layer's agreement with the spec is computed with the same quote-aware parser the run uses, so a parser fault would make both readings wrong together. Covered by the naive-split histogram, a structurally different reading of the same bytes.",
    "Nothing here can detect a systematic MISREADING of the neutral spec: every check is built from the same reading of it. Only the source-side comparison can, and the source's values are withheld until after this emission by design.",
    "The good/bad fixtures are hand-built, so they calibrate the checks against defects that were thought of. They cannot calibrate against a defect nobody imagined (R15: a threshold calibrated on synthetic data is not calibrated).",
    "The abort path is exercised by its own probe input, not here: a poisoned row placed in these fixtures would halt the fixture run rather than produce a verdict.",
  ];

  const passed = results.filter((r) => r.ok).length;
  return { results, passed, failed: results.length - passed, blindSpots, separation };
}

type Status2 = "PASS" | "FLAGGED" | "FAIL" | "NOT_EXERCISED";

function isoOf(day: number): string {
  const c = civilFromDays(day);
  const p2 = (n: number) => (n < 10 ? "0" + intText(n) : intText(n));
  let y = intText(c.y);
  while (y.length < 4) y = "0" + y;
  return y + "-" + p2(c.m) + "-" + p2(c.d);
}

/** The rule the spec warns against, kept only so the self-test can show it differs. */
function naiveMultiplyRoundDivide(x: number, d: number): number {
  const p = Math.pow(10, d);
  const y = x * p;
  const f = Math.floor(y);
  const frac = y - f;
  let r: number;
  if (frac > 0.5) r = f + 1;
  else if (frac < 0.5) r = f;
  else r = f % 2 === 0 ? f : f + 1;
  return r / p;
}
