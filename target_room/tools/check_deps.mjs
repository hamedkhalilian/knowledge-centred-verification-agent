// Dependency budget gate (GR-01, target directive 3): zero runtime dependencies,
// and exactly one allow-listed build-time dependency, the TypeScript compiler.
import { readFileSync } from "node:fs";
const p = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const deps = Object.keys(p.dependencies ?? {});
const dev = Object.keys(p.devDependencies ?? {});
const allow = ["typescript"];
let bad = 0;
if (deps.length) { console.error("[build] runtime dependencies present: " + deps.join(", ")); bad = 1; }
const extra = dev.filter((d) => !allow.includes(d));
if (extra.length) { console.error("[build] build-time dependencies beyond the allow-list: " + extra.join(", ")); bad = 1; }
if (!bad) console.log("[build] dependency budget: 0 runtime, " + dev.length + " build-time (" + dev.join(", ") + "), allow-list " + allow.join(", "));
process.exit(bad);
