#!/usr/bin/env python3
"""Controller cross-check (R3 gate): mechanically-parsed source field groups
vs the neutral spec's declared name vectors.

The detector is SOURCE_OBSERVATION_ONLY -- it verifies, it never configures.

Run 2's single checkpoint divergence came from a spec that stated a decisive
name list as a count plus constraints instead of as values (lessons, finding 2).
This gate exists to make that impossible. For it to do that, it must be
impossible for the gate to pass without having actually compared something:

  * an empty detector output is a FAILED gate, not three silent agreements;
  * a pair that is empty on both sides is a FAILED gate, not an agreement;
  * a list-valued constant in the spec that no binding covers is a FAILED gate,
    because an uncompared name vector is exactly the run-2 defect;
  * a detector group that no binding covers is a FAILED gate, for the same
    reason in the other direction.

Which file, which unit and which group/constant pairs to compare are declared
per run in a bindings file -- they are NOT baked into this tool. A gate
hard-wired to one run's names passes vacuously on every other run, which is
lessons finding 7 (a controller detector never exercised on different
known-good input) reappearing in the tool that finding 2 asked for.

Usage
-----
  check_detector_vs_spec.py [--detector CSV] [--spec JSON] [--bindings JSON]

Exit codes
----------
  0  every declared comparison ran and agreed
  1  a real divergence: detector and spec disagree on a name vector
  2  the gate could not run meaningfully (misconfiguration, or a vacuous
     comparison). Distinct from 1 on purpose: "nothing to compare" must never
     be reportable as "compared and agreed".
"""
import argparse
import csv
import json
import os
import sys

DEFAULT_DETECTOR = "evidence/source_detector/r_source_field_groups.csv"
DEFAULT_SPEC = "source_room/out/neutral_spec.json"
DEFAULT_BINDINGS = "contracts/detector_spec_bindings.json"

REQUIRED_DETECTOR_COLUMNS = {"file", "group", "ordinal", "field"}


class GateError(Exception):
    """The gate cannot run meaningfully. Always exit 2, never 0."""


def load_detector_groups(path, source_file):
    """Return {group: [field, ...]} for one source file, ordered by ordinal."""
    if not os.path.exists(path):
        raise GateError("detector output not found: %s" % path)
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        columns = set(reader.fieldnames or [])
        if not REQUIRED_DETECTOR_COLUMNS.issubset(columns):
            raise GateError(
                "detector output %s lacks required columns %s (found: %s). "
                "An empty or malformed detector file is a failed gate, not an "
                "agreement." % (
                    path,
                    sorted(REQUIRED_DETECTOR_COLUMNS - columns),
                    sorted(columns) or "none",
                )
            )
        rows = [r for r in reader if r.get("file") == source_file]
    groups = {}
    for row in rows:
        try:
            ordinal = int(row["ordinal"])
        except (TypeError, ValueError):
            raise GateError(
                "detector row for %s has a non-integer ordinal %r; the "
                "comparison is order-sensitive and cannot proceed."
                % (source_file, row.get("ordinal"))
            )
        groups.setdefault(row["group"], []).append((ordinal, row["field"]))
    return {g: [f for _, f in sorted(v)] for g, v in groups.items()}


def load_spec_vectors(path, unit_id):
    """Return {constant_name: [values]} for the list-valued constants of a unit."""
    if not os.path.exists(path):
        raise GateError("neutral spec not found: %s" % path)
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    units = [u for u in spec.get("units", []) if u.get("id") == unit_id]
    if not units:
        raise GateError(
            "neutral spec %s declares no unit %r (units present: %s)"
            % (path, unit_id, [u.get("id") for u in spec.get("units", [])] or "none")
        )
    if len(units) > 1:
        raise GateError("neutral spec %s declares unit %r more than once" % (path, unit_id))
    return {
        c["name"]: c["value"]
        for c in units[0].get("constants", [])
        if isinstance(c.get("value"), list)
    }


def check_binding(binding, detector_path, spec_path):
    """Run one binding. Return (divergences, gate_errors, lines_to_print)."""
    source_file = binding["source_file"]
    unit_id = binding["unit"]
    pairs = binding.get("pairs", [])
    waived_groups = set(binding.get("waived_detector_groups", []))
    waived_constants = set(binding.get("waived_spec_constants", []))

    out = ["", "=== %s -> unit %s ===" % (source_file, unit_id)]
    detected = load_detector_groups(detector_path, source_file)
    declared = load_spec_vectors(spec_path, unit_id)

    if not detected:
        raise GateError(
            "the detector reports no field groups for %s. Either the file was "
            "not in the detector's scope, or it did not parse. Neither is an "
            "agreement." % source_file
        )
    if not pairs:
        raise GateError("binding for %s declares no pairs to compare" % source_file)

    divergences, errors = [], []
    seen_groups, seen_constants = set(), set()

    for pair in pairs:
        group = pair["detector_group"]
        constant = pair["spec_constant"]
        seen_groups.add(group)
        seen_constants.add(constant)
        left = detected.get(group)
        right = declared.get(constant)

        if left is None and right is None:
            errors.append(
                "VACUOUS  %s vs %s -- neither side exists. A comparison with "
                "nothing on either side is not an agreement." % (group, constant)
            )
            continue
        if left is None:
            divergences.append("MISSING  detector group %r not observed in %s" % (group, source_file))
            out.append("DIFFER  %s (absent) vs spec %s (%d)" % (group, constant, len(right)))
            continue
        if right is None:
            divergences.append("MISSING  spec constant %r not declared in unit %s" % (constant, unit_id))
            out.append("DIFFER  %s (%d) vs spec %s (absent)" % (group, len(left), constant))
            continue

        if left == right:
            out.append("AGREE   %s (%d) vs spec %s (%d)" % (group, len(left), constant, len(right)))
            continue

        out.append("DIFFER  %s (%d) vs spec %s (%d)" % (group, len(left), constant, len(right)))
        only_detector = [v for v in left if v not in right]
        only_spec = [v for v in right if v not in left]
        if not only_detector and not only_spec:
            out.append("   same values, DIFFERENT ORDER")
            out.append("   detector: %s" % left)
            out.append("   spec    : %s" % right)
        else:
            out.append("   only in detector: %s" % sorted(only_detector))
            out.append("   only in spec    : %s" % sorted(only_spec))
        divergences.append("%s vs %s" % (group, constant))

    uncovered_constants = sorted(set(declared) - seen_constants - waived_constants)
    if uncovered_constants:
        errors.append(
            "UNCOVERED  unit %s declares name vector(s) %s that no binding "
            "compares. An uncompared name vector is the run-2 defect; bind it "
            "or waive it explicitly." % (unit_id, uncovered_constants)
        )
    uncovered_groups = sorted(set(detected) - seen_groups - waived_groups)
    if uncovered_groups:
        errors.append(
            "UNCOVERED  the detector observed group(s) %s in %s that no "
            "binding compares. Bind them or waive them explicitly."
            % (uncovered_groups, source_file)
        )
    return divergences, errors, out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--detector", default=DEFAULT_DETECTOR, help="detector field-groups CSV")
    parser.add_argument("--spec", default=DEFAULT_SPEC, help="neutral spec JSON")
    parser.add_argument("--bindings", default=DEFAULT_BINDINGS, help="per-run bindings JSON")
    # Positional forms kept so existing controller_flow invocations keep working.
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    detector_path, spec_path = args.detector, args.spec
    if len(args.positional) >= 1:
        detector_path = args.positional[0]
    if len(args.positional) >= 2:
        spec_path = args.positional[1]
    if len(args.positional) >= 3:
        args.bindings = args.positional[2]

    try:
        if not os.path.exists(args.bindings):
            raise GateError(
                "bindings file not found: %s. This gate is declared per run: it "
                "must be told which source file, which spec unit, and which "
                "group/constant pairs to compare." % args.bindings
            )
        with open(args.bindings, encoding="utf-8") as fh:
            config = json.load(fh)
        bindings = config.get("bindings", [])
        if not bindings:
            raise GateError("%s declares no bindings; the gate has nothing to check" % args.bindings)

        all_divergences, all_errors, lines = [], [], []
        for binding in bindings:
            divergences, errors, out = check_binding(binding, detector_path, spec_path)
            all_divergences += divergences
            all_errors += errors
            lines += out
    except GateError as exc:
        print("GATE ERROR: %s" % exc, file=sys.stderr)
        return 2
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print("GATE ERROR: malformed configuration or artifact: %s" % exc, file=sys.stderr)
        return 2

    for line in lines:
        print(line)

    run_id = config.get("run_id", "(unnamed run)")
    compared = sum(len(b.get("pairs", [])) for b in bindings)
    print("")
    if all_errors:
        for err in all_errors:
            print(err)
        print("\nR3 GATE FAILED TO RUN (%s): %d pair(s) declared, but the gate "
              "could not compare them meaningfully." % (run_id, compared))
        return 2
    if all_divergences:
        print("R3 GATE DIVERGENCE (%s): %d of %d declared pair(s) disagree."
              % (run_id, len(all_divergences), compared))
        return 1
    print("R3 GATE PASSED (%s): %d declared pair(s) compared, all agree." % (run_id, compared))
    print("Scope note: this gate compares declared name vectors only. It makes "
          "no claim about checkpoint agreement -- that is COMPARE's evidence, "
          "produced by compare_checkpoints.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
