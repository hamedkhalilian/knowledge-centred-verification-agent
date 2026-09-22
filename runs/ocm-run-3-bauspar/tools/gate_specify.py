#!/usr/bin/env python3
"""Controller SPECIFY exit gate -- run 3.

"The controller executes every gate itself. An agent's report of a green check
is not a green check." (controller brief; lessons finding 8.) This runs all
three gates and records one verdict, so no gate can be skipped by being
forgotten.

Gates, in order:
  1. BARRIER   -- no source-language syntax in artifacts that cross to the
                  target room. The scanner self-validates on a known leak each
                  run; if the leak stops firing, the scan means nothing.
  2. SCHEMA    -- every artifact validates against its schema.
  3. R3        -- every decisive name vector the spec declares agrees with a
                  mechanical parse of the source, and none is left uncompared.

Exit codes are three-valued, matching the R3 gate:
  0  every gate ran and passed
  1  a gate ran and found a real problem -> route it (spec defect, usually)
  2  a gate could NOT run -> halt. Never reportable as a pass.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KIT = os.path.join(ROOT, "ocm-kit")

PASS, FAIL, CANNOT_RUN = 0, 1, 2
LABEL = {PASS: "PASS", FAIL: "FAIL", CANNOT_RUN: "CANNOT RUN"}


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def banner(title):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def gate_barrier(artifacts):
    banner("GATE 1/3  BARRIER -- source-language syntax must not cross")
    present = [a for a in artifacts if os.path.exists(os.path.join(ROOT, a))]
    missing = [a for a in artifacts if a not in present]
    for m in missing:
        print("  missing artifact: %s" % m)
    if not present:
        print("\nNo artifact to scan. A barrier scan over nothing is not a clean scan.")
        return CANNOT_RUN, "no artifacts present"
    code, out = run([sys.executable, os.path.join(KIT, "tools", "scan_barrier.py")] + present)
    print(out.rstrip())
    if "leak-injection validation" not in out:
        return CANNOT_RUN, "scanner did not self-validate; its verdict means nothing"
    if code == 2:
        return CANNOT_RUN, "scanner declared itself invalid"
    if missing:
        return CANNOT_RUN, "scanned only %d of %d artifacts" % (len(present), len(artifacts))
    return (PASS, "clean") if code == 0 else (FAIL, "source-language syntax found")


def gate_schema(pairs):
    banner("GATE 2/3  SCHEMA -- artifacts must validate")
    try:
        import jsonschema
    except ImportError:
        return CANNOT_RUN, "jsonschema not installed"
    worst, notes = PASS, []
    checked = 0
    for artifact, schema_name in pairs:
        apath = os.path.join(ROOT, artifact)
        spath = os.path.join(KIT, "contracts", "schemas", schema_name)
        if not os.path.exists(apath):
            print("  MISSING  %s" % artifact)
            worst = max(worst, CANNOT_RUN)
            notes.append("%s absent" % os.path.basename(artifact))
            continue
        if not os.path.exists(spath):
            print("  NO SCHEMA %s" % schema_name)
            worst = max(worst, CANNOT_RUN)
            notes.append("%s missing" % schema_name)
            continue
        try:
            doc = json.load(open(apath, encoding="utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            print("  UNPARSABLE %s: %s" % (artifact, exc))
            worst = max(worst, CANNOT_RUN)
            notes.append("%s unparsable" % os.path.basename(artifact))
            continue
        schema = json.load(open(spath, encoding="utf-8"))
        errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc),
                        key=lambda e: list(e.path))
        if errors:
            print("  INVALID  %s (%d errors against %s)" % (artifact, len(errors), schema_name))
            for err in errors[:12]:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                print("     %s: %s" % (loc, err.message[:160]))
            if len(errors) > 12:
                print("     ... %d more" % (len(errors) - 12))
            worst = max(worst, FAIL) if worst != CANNOT_RUN else CANNOT_RUN
            notes.append("%s invalid" % os.path.basename(artifact))
        else:
            print("  VALID    %s  against %s" % (artifact, schema_name))
            checked += 1
    if checked == 0 and worst == PASS:
        return CANNOT_RUN, "nothing was validated"
    return worst, "; ".join(notes) if notes else "%d artifact(s) valid" % checked


def gate_r3(detector, spec, bindings):
    banner("GATE 3/3  R3 -- declared name vectors vs a mechanical parse")
    code, out = run([sys.executable,
                     os.path.join(KIT, "tools", "check_detector_vs_spec.py"),
                     "--detector", detector, "--spec", spec, "--bindings", bindings])
    print(out.rstrip())
    return code, {PASS: "all declared vectors agree",
                  FAIL: "a declared vector diverges",
                  CANNOT_RUN: "the gate could not compare"}.get(code, "unknown")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--spec-dir", default="runs/ocm-run-3-bauspar/spec")
    p.add_argument("--detector",
                   default="runs/ocm-run-3-bauspar/evidence/source_detector/derived_field_groups.csv")
    p.add_argument("--bindings", default="ocm-kit/contracts/detector_spec_bindings.json")
    p.add_argument("--out", default="runs/ocm-run-3-bauspar/evidence/gate_specify_result.json")
    args = p.parse_args()

    spec = os.path.join(args.spec_dir, "neutral_spec.json")
    manifest = os.path.join(args.spec_dir, "flow_manifest_source.json")

    crossing = [spec]
    if os.path.exists(os.path.join(ROOT, manifest)):
        crossing.append(manifest)

    schema_pairs = [(spec, "neutral_spec_schema.json")]
    if os.path.exists(os.path.join(ROOT, manifest)):
        schema_pairs.append((manifest, "flow_manifest_schema.json"))

    results = {}
    results["barrier"] = gate_barrier(crossing)
    results["schema"] = gate_schema(schema_pairs)
    results["r3"] = gate_r3(args.detector, spec, args.bindings)

    banner("SPECIFY EXIT GATE -- controller verdict")
    worst = PASS
    for name in ("barrier", "schema", "r3"):
        code, note = results[name]
        print("  %-8s %-11s %s" % (name, LABEL.get(code, code), note))
        worst = max(worst, code)

    if worst == PASS:
        print("\nSPECIFY may exit. The spec is releasable to the target room.")
    elif worst == FAIL:
        print("\nSPECIFY BLOCKED: a gate found a real defect. Route it -- do not "
              "release, and do not fix it on the target side.")
    else:
        print("\nSPECIFY HALTED: a gate could not run. This is NOT a pass. "
              "Nothing may cross until every gate has actually executed.")

    record = {
        "run_id": "ocm-run-3-bauspar",
        "state": "SPECIFY",
        "gates": {k: {"result": LABEL.get(v[0], v[0]), "note": v[1]} for k, v in results.items()},
        "verdict": LABEL.get(worst, worst),
        "releasable_to_target": worst == PASS,
    }
    outpath = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    print("\nrecorded -> %s" % args.out)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
