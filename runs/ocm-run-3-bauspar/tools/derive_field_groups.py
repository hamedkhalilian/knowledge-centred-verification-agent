#!/usr/bin/env python3
"""Adapt the R detector's column-usage output into field-groups shape, so the
R3 gate can actually compare this source's decisive vectors.

WHY THIS EXISTS
---------------
The R3 gate (ocm-kit/tools/check_detector_vs_spec.py) reads
r_source_field_groups.csv. The detector populates that file only from literal
character vectors assigned to a name matching cols/columns/names -- run 2's
idiom, where a column catalogue was written out as a literal vector.

This source does not have one. Its input contract is expressed as direct
named accesses on a contract row, so r_source_field_groups.csv comes out
EMPTY -- correctly. The detector is not failing here; the catalogue simply
lives in r_source_column_usage.csv instead, under a different shape.

Left alone, that is how a gate ends up with nothing to compare. The rewritten
gate now refuses to pass on an empty detector file, so it would halt the run
rather than wave it through -- the right failure, but still a halt. This
adapter supplies the vector the gate should have been comparing all along.

ORDER
-----
The gate is order-sensitive, deliberately: for a positional layout, order is
semantic and a reordering is a real defect. For a catalogue of columns
accessed BY NAME, order carries no meaning -- the engine would behave
identically if they were declared in any sequence.

So this adapter emits them sorted bytewise ascending, and the spec is expected
to declare them in that same order. This is a stated convention, not a
discovered fact. If the spec declares the same eleven names in a different
order, the gate reports "same values, DIFFERENT ORDER", which is exactly the
signal a human should adjudicate rather than a failure to paper over.

Usage:
  derive_field_groups.py --column-usage <csv> --out <csv> [--object contract]
"""
import argparse
import collections
import csv
import os
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--column-usage",
                        default="runs/ocm-run-3-bauspar/evidence/source_detector/r_source_column_usage.csv")
    parser.add_argument("--out",
                        default="runs/ocm-run-3-bauspar/evidence/source_detector/derived_field_groups.csv")
    parser.add_argument("--object", action="append", default=None,
                        help="restrict to these accessed objects (repeatable); "
                             "default: every object the detector saw")
    parser.add_argument("--group-suffix", default="_input_columns",
                        help="group name is <object><suffix>")
    args = parser.parse_args()

    if not os.path.exists(args.column_usage):
        print("no column-usage file at %s" % args.column_usage, file=sys.stderr)
        return 2

    with open(args.column_usage, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("column-usage file %s has no rows; nothing to derive"
              % args.column_usage, file=sys.stderr)
        return 2

    wanted = set(args.object) if args.object else None
    by_key = collections.defaultdict(set)
    for row in rows:
        obj = (row.get("object") or "").strip()
        field = (row.get("field") or "").strip()
        src = (row.get("file") or "").strip()
        if not obj or not field:
            continue
        if wanted is not None and obj not in wanted:
            continue
        by_key[(src, obj)].add(field)

    if not by_key:
        print("no (object, field) pairs matched%s"
              % ("" if wanted is None else " for objects %s" % sorted(wanted)),
              file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    written = 0
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["file", "group", "ordinal", "field"])
        for (src, obj) in sorted(by_key):
            group = "%s%s" % (obj, args.group_suffix)
            for ordinal, field in enumerate(sorted(by_key[(src, obj)]), 1):
                writer.writerow([src, group, ordinal, field])
                written += 1

    print("wrote %s (%d rows)" % (args.out, written))
    for (src, obj) in sorted(by_key):
        print("  %s / %s%s: %d fields -> %s"
              % (src, obj, args.group_suffix, len(by_key[(src, obj)]),
                 sorted(by_key[(src, obj)])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
