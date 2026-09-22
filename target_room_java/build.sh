#!/usr/bin/env bash
# build.sh -- R13: compile at the level the project DECLARES, read from the
# project's own settings. The level is never written as a literal here.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROPS="$HERE/project.properties"

if [ ! -f "$PROPS" ]; then
  echo "build.sh: FAIL -- $PROPS not found; the declared level has no source (R13)." >&2
  exit 2
fi

readprop() {
  # raw line parser (GR-02): never Properties-style escape handling.
  sed -n -E "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*(.*)$/\1/p" "$PROPS" | head -1 | sed -E 's/[[:space:]]+$//'
}

LEVEL="$(readprop 'java\.level')"
SRCDIR="$(readprop 'source\.dir')"
OUTDIR="$(readprop 'output\.dir')"
ALLOW="$(readprop 'bigdecimal\.allowlist')"

if [ -z "$LEVEL" ]; then
  echo "build.sh: FAIL -- java.level absent from project.properties (R13)." >&2
  exit 2
fi
echo "build.sh: declared java.level=$LEVEL   (read from project.properties, not restated)"
echo "build.sh: javac  -> $(javac -version 2>&1)"
echo "build.sh: java   -> $(java -version 2>&1 | head -1)"

# ---- GR-11 gate: BigDecimal may appear ONLY in the declared allow-list -----
echo "build.sh: GR-11 gate -- scanning for BigDecimal outside the allow-list ($ALLOW)"
VIOLATIONS=0
while IFS= read -r f; do
  rel="${f#$HERE/}"
  if grep -q 'BigDecimal' "$f"; then
    if [ "$rel" != "$ALLOW" ]; then
      echo "build.sh: GR-11 VIOLATION -- BigDecimal in $rel" >&2
      VIOLATIONS=$((VIOLATIONS+1))
    else
      echo "build.sh: GR-11 ok       -- BigDecimal in $rel (allow-listed serialiser)"
    fi
  fi
done < <(find "$HERE/$SRCDIR" -name '*.java' | sort)
if [ "$VIOLATIONS" -ne 0 ]; then
  echo "build.sh: FAIL -- $VIOLATIONS BigDecimal violation(s) in computation paths (GR-11)." >&2
  exit 3
fi
echo "build.sh: GR-11 gate PASS ($VIOLATIONS violations)"

# ---- dependency budget gate: JDK only --------------------------------------
if grep -rnE '^import[[:space:]]+(?!java\.|javax\.)' --perl-regexp "$HERE/$SRCDIR" >/dev/null 2>&1; then
  echo "build.sh: GR-01 VIOLATION -- non-JDK import found:" >&2
  grep -rnE --perl-regexp '^import[[:space:]]+(?!java\.|javax\.)' "$HERE/$SRCDIR" >&2
  exit 4
fi
echo "build.sh: GR-01 gate PASS (JDK-only imports)"

rm -rf "${HERE:?}/$OUTDIR"
mkdir -p "$HERE/$OUTDIR"
mapfile -t SRCS < <(find "$HERE/$SRCDIR" -name '*.java' | sort)
echo "build.sh: compiling ${#SRCS[@]} source files"
set -x
javac --release "$LEVEL" -Xlint:all -d "$HERE/$OUTDIR" "${SRCS[@]}"
set +x
echo "build.sh: OK -- classes in $HERE/$OUTDIR"
