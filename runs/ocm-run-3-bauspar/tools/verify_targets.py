#!/usr/bin/env python3
"""Rebuild each target and assert its checkpoint digests still match the source.

WHY THIS EXISTS
---------------
Run 3 established that three implementations -- the R source, a TypeScript
target and a Java target, written in separate contexts from the same neutral
spec -- produce byte-identical checkpoints. That was a one-time result held in
a comparison artifact.

Nothing re-checked it. The repository's CI ran the Python suite and the ledger
validations; neither builds a target. An edit to the export mapping or the
canonicalisation in either target would break the agreement and CI would stay
green, because no test reaches that code.

This turns the result into a regression test: build each target from source,
run it on the staged input, and compare its three digests against the committed
source checkpoints. A target that no longer agrees fails the build.

EXIT CODES, three-valued, as every other gate in this run
--------------------------------------------------------
  0  every requested target was built, ran, and agrees
  1  a target ran and DISAGREES -- a real regression
  2  a target could not be built or run, so nothing was established

Exit 2 is distinct from 0 on purpose. A verifier that cannot verify must never
be reportable as agreement -- the failure this run found in the R3 gate, in
COMPARE, and in two of its own detectors.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOURCE_CHECKPOINTS = os.path.join(ROOT, "runs", "ocm-run-3-bauspar", "evidence",
                                  "checkpoints_source.json")
STAGED_INPUT = os.path.join(ROOT, "staged_inputs", "merged_data_synthetic.csv")

PASS, REGRESSION, CANNOT_RUN = 0, 1, 2


class CannotRun(Exception):
    """The TOOLCHAIN is unavailable, so nothing was established. Exit 2."""


class Broken(Exception):
    """The target is present but does not build, or refuses to run. Exit 1.

    Distinguishing these two matters. A missing compiler says nothing about the
    code; a target that compiles and then aborts is a regression, and the most
    likely reason is the one this run cares about -- the canonicalisation
    contract obliges each emitter to self-test its reference vectors at startup
    and abort on mismatch, so a broken target refuses to emit rather than
    emitting something wrong.

    Verified by injecting one: changing a single threshold in the Java engine
    made its own self-test report 93/94 RED and exit before writing anything.
    The first version of this script logged that as "could not run", which
    understated it -- the target had not failed to run, it had correctly
    refused to."""


def digests(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return {o["name"]: o["digest"]["value"] for o in doc["units"][0]["objects"]}


def run(cmd, cwd=None, what="", broken_if_fails=True):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = "%s failed (exit %d)\n%s" % (what, proc.returncode,
                 ((proc.stdout or "") + (proc.stderr or ""))[:4000])
        raise (Broken if broken_if_fails else CannotRun)(detail)
    return proc.stdout


def verify_java(outdir):
    room = os.path.join(ROOT, "target_room_java")
    if not shutil.which("javac"):
        raise CannotRun("javac is not on PATH")
    run(["bash", "build.sh"], cwd=room, what="java build.sh")
    run(["java", "-cp", os.path.join(room, "bin"), "bauspar.Main",
         STAGED_INPUT, "--out=%s" % outdir], cwd=ROOT, what="java run")
    return os.path.join(outdir, "checkpoints_target.json")


def verify_typescript(outdir):
    room = os.path.join(ROOT, "target_room")
    if not shutil.which("node"):
        raise CannotRun("node is not on PATH")
    if not os.path.isdir(os.path.join(room, "node_modules")):
        if not shutil.which("npm"):
            raise CannotRun("npm is not on PATH and node_modules is absent")
        # A failed dependency fetch is an environment problem, not a regression.
        run(["npm", "install", "--no-audit", "--no-fund"], cwd=room,
            what="npm install", broken_if_fails=False)
    run(["bash", "build.sh"], cwd=room, what="typescript build.sh")
    run(["node", os.path.join(room, "dist", "index.js"), STAGED_INPUT,
         "--evidence-dir", outdir], cwd=ROOT, what="typescript run")
    return os.path.join(outdir, "checkpoints_target.json")


TARGETS = {"java": verify_java, "typescript": verify_typescript}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", action="append", choices=sorted(TARGETS) + ["all"],
                        help="repeatable; default all")
    args = parser.parse_args()
    wanted = sorted(TARGETS) if not args.target or "all" in args.target else sorted(set(args.target))

    if not os.path.exists(SOURCE_CHECKPOINTS):
        print("GATE ERROR: source checkpoints not found at %s" % SOURCE_CHECKPOINTS,
              file=sys.stderr)
        return CANNOT_RUN
    if not os.path.exists(STAGED_INPUT):
        print("GATE ERROR: staged input not found at %s.\n"
              "It is generated, not committed: run\n"
              "  python3 runs/ocm-run-3-bauspar/tools/gen_synthetic_bauspar.py "
              "--out-dir staged_inputs" % STAGED_INPUT, file=sys.stderr)
        return CANNOT_RUN

    expected = digests(SOURCE_CHECKPOINTS)
    worst = PASS
    for name in wanted:
        print("\n=== %s ===" % name)
        tmp = tempfile.mkdtemp(prefix="verify-%s-" % name)
        try:
            produced = digests(TARGETS[name](tmp))
        except Broken as exc:
            print("BROKEN: %s" % exc, file=sys.stderr)
            print("  The target built or was present but did not produce checkpoints. "
                  "If its self-test aborted, that IS the regression: the emitter is "
                  "required to refuse rather than emit something wrong.", file=sys.stderr)
            worst = max(worst, REGRESSION)
            continue
        except CannotRun as exc:
            print("CANNOT RUN: %s" % exc, file=sys.stderr)
            worst = max(worst, CANNOT_RUN)
            continue
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        missing = sorted(set(expected) - set(produced))
        extra = sorted(set(produced) - set(expected))
        if missing or extra:
            print("  object sets differ -- missing %s, unexpected %s" % (missing, extra))
            worst = max(worst, REGRESSION)
            continue
        bad = [k for k in sorted(expected) if expected[k] != produced[k]]
        for k in sorted(expected):
            print("  %-24s %s" % (k, "agrees" if k not in bad else "DIFFERS"))
            if k in bad:
                print("      source: %s" % expected[k])
                print("      %-6s: %s" % (name, produced[k]))
        if bad:
            worst = max(worst, REGRESSION)

    print("")
    if worst == PASS:
        print("ALL TARGETS AGREE with the committed source checkpoints (%s)."
              % ", ".join(wanted))
    elif worst == REGRESSION:
        print("REGRESSION: a target no longer reproduces the source's checkpoints, "
              "or refused to emit them.")
    else:
        print("NOT ESTABLISHED: a target could not be built or run. This is NOT a pass.")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
