// Reads the DECLARED language level out of tsconfig.json (R13).
// The level is written once, in the project's own settings, and the build script
// reads it from there so the two cannot drift apart. It is never restated as a
// literal anywhere else (target directive 2).
import { readFileSync } from "node:fs";
const raw = readFileSync(new URL("../tsconfig.json", import.meta.url), "utf8");
// tsconfig admits comments; strip line comments before parsing.
const json = JSON.parse(raw.replace(/^\s*\/\/.*$/gm, ""));
const co = json.compilerOptions ?? {};
const key = process.argv[2];
const v = co[key];
if (v === undefined) {
  console.error(`tsconfig.json declares no compilerOptions.${key}`);
  process.exit(1);
}
process.stdout.write(String(v));
