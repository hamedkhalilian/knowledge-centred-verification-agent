#!/usr/bin/env bash
# Build at the DECLARED level, read from the project's own settings (R13).
#
# The level is written once, in tsconfig.json. This script reads it from there
# and passes it to the compiler explicitly, so a build can never be green at a
# level the project did not declare. It then re-reads the compiler's EFFECTIVE
# configuration and asserts the two agree -- consulting an authority is not the
# same as executing against it.
set -euo pipefail
cd "$(dirname "$0")"

TARGET="$(node tools/read_level.mjs target)"
MODULE="$(node tools/read_level.mjs module)"
STRICT="$(node tools/read_level.mjs strict)"
echo "[build] declared level read from tsconfig.json: target=${TARGET} module=${MODULE} strict=${STRICT}"

if [ "${STRICT}" != "true" ]; then
  echo "[build] tsconfig.json does not declare strict:true; refusing to build" >&2
  exit 1
fi

TSC="./node_modules/.bin/tsc"
echo "[build] compiler: $("${TSC}" --version)"

rm -rf dist
echo "[build] + ${TSC} --project tsconfig.json --target ${TARGET} --module ${MODULE} --strict --noEmitOnError"
"${TSC}" --project tsconfig.json --target "${TARGET}" --module "${MODULE}" --strict --noEmitOnError

EFF_TARGET="$("${TSC}" --project tsconfig.json --showConfig | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>process.stdout.write(String(JSON.parse(s).compilerOptions.target)))')"
EFF_MODULE="$("${TSC}" --project tsconfig.json --showConfig | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>process.stdout.write(String(JSON.parse(s).compilerOptions.module)))')"
echo "[build] effective configuration reported by the compiler: target=${EFF_TARGET} module=${EFF_MODULE}"
if [ "$(printf '%s' "${EFF_TARGET}" | tr 'A-Z' 'a-z')" != "$(printf '%s' "${TARGET}" | tr 'A-Z' 'a-z')" ]; then
  echo "[build] effective target ${EFF_TARGET} != declared ${TARGET}" >&2; exit 1
fi
if [ "$(printf '%s' "${EFF_MODULE}" | tr 'A-Z' 'a-z')" != "$(printf '%s' "${MODULE}" | tr 'A-Z' 'a-z')" ]; then
  echo "[build] effective module ${EFF_MODULE} != declared ${MODULE}" >&2; exit 1
fi

node tools/scan_number_formatting.mjs

# Dependency budget (GR-01, target directive 3): zero runtime dependencies.
node tools/check_deps.mjs

echo "[build] ok"
