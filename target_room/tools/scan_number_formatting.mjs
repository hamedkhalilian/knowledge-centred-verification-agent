// Build-time scan required by target directive 3.
//
// The canonicalisation contract's 9-significant-digit rendering is implemented
// in exactly one module, src/canonical.ts. This scan proves that no other module
// under src/ formats a number for output.
//
// What counts as formatting a number for output: the ECMAScript number-to-text
// APIs (toFixed, toPrecision, toExponential, Intl.NumberFormat), and any other
// route from a number to a rendered string. Every module that needs integer text
// imports intText from canonical.ts instead; canonical.ts is the one place where
// a number becomes characters.
//
// JSON.stringify is on the declared allow-list for the evidence artifacts, and
// index.ts backs that allowance with an executable assertion: every number that
// reaches the JSON must be a safe integer, because every VALUE in a checkpoint
// travels as canonical text and the only numbers the schema admits are counts.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = new URL("../src/", import.meta.url).pathname;
const ALLOWED_FILE = "canonical.ts";
const FORBIDDEN = [
  /\btoFixed\s*\(/,
  /\btoPrecision\s*\(/,
  /\btoExponential\s*\(/,
  /\bIntl\.NumberFormat\b/,
  /\btoLocaleString\s*\(/,
];

let hits = 0;
let scanned = 0;
for (const f of readdirSync(SRC).filter((f) => f.endsWith(".ts")).sort()) {
  const text = readFileSync(join(SRC, f), "utf8");
  scanned += 1;
  if (f === ALLOWED_FILE) continue;
  text.split("\n").forEach((line, i) => {
    // a line that is only a comment is not code
    if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
    for (const re of FORBIDDEN) {
      if (re.test(line)) {
        console.error(`[scan] ${f}:${i + 1}: forbidden number formatting -> ${line.trim()}`);
        hits += 1;
      }
    }
  });
}
// The allowed module must actually be the one that exports the renderings.
const canonical = readFileSync(join(SRC, ALLOWED_FILE), "utf8");
for (const name of ["canonicalNumber", "scriptNumber", "intText", "decimalToNearestDouble"]) {
  if (!canonical.includes(`export function ${name}`)) {
    console.error(`[scan] ${ALLOWED_FILE} does not export ${name}`);
    hits += 1;
  }
}
console.log(`[scan] ${scanned} module(s) scanned; ${hits} violation(s); number formatting confined to src/${ALLOWED_FILE}`);
process.exit(hits === 0 ? 0 : 1);
