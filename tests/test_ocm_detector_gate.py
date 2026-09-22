"""Tests for the OCM R3 gate (ocm-kit/tools/check_detector_vs_spec.py).

The gate exists because run 2's single checkpoint divergence came from a spec
that stated a decisive name list as a count instead of as values. Its own
failure mode is subtler: hard-wired to one run's names, it compares nothing and
reports agreement. These tests pin both halves -- it must catch the divergence
it was built for, and it must refuse to pass when it compared nothing.
"""
import csv
import sys
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "ocm-kit" / "tools" / "check_detector_vs_spec.py"

EXIT_AGREE = 0
EXIT_DIVERGENCE = 1
EXIT_CANNOT_RUN = 2


def load_gate():
    spec = importlib.util.spec_from_file_location("ocm_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GateHarness(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write_detector(self, rows, name="detector.csv", header=True):
        path = self.tmp / name
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if header:
                writer.writerow(["file", "group", "ordinal", "field"])
            writer.writerows(rows)
        return path

    def write_spec(self, constants, unit="U01", name="spec.json"):
        path = self.tmp / name
        payload = {"units": [{"id": unit, "constants": [
            {"name": k, "value": v} for k, v in constants.items()]}]}
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_bindings(self, bindings, name="bindings.json", run_id="test-run"):
        path = self.tmp / name
        path.write_text(json.dumps({"run_id": run_id, "bindings": bindings}), encoding="utf-8")
        return path

    def run_gate(self, detector, spec, bindings):
        return self.gate.main(["--detector", str(detector), "--spec", str(spec),
                               "--bindings", str(bindings)])

    def simple_binding(self, source_file="u.R", unit="U01",
                       group="g_cols", constant="k_fields", **extra):
        binding = {"source_file": source_file, "unit": unit,
                   "pairs": [{"detector_group": group, "spec_constant": constant}]}
        binding.update(extra)
        return [binding]


class TestGateCatchesDivergence(GateHarness):
    def test_matching_vectors_agree(self):
        detector = self.write_detector([
            ["u.R", "g_cols", 1, "alpha"],
            ["u.R", "g_cols", 2, "beta"],
        ])
        spec = self.write_spec({"k_fields": ["alpha", "beta"]})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_AGREE)

    def test_run2_defect_right_count_wrong_values(self):
        """The exact run-2 divergence: the count matches, a value is guessed."""
        detector = self.write_detector([
            ["u.R", "g_cols", 1, "alpha"],
            ["u.R", "g_cols", 2, "beta"],
        ])
        spec = self.write_spec({"k_fields": ["alpha", "delta"]})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_DIVERGENCE)

    def test_same_values_different_order_is_a_divergence(self):
        detector = self.write_detector([
            ["u.R", "g_cols", 1, "alpha"],
            ["u.R", "g_cols", 2, "beta"],
        ])
        spec = self.write_spec({"k_fields": ["beta", "alpha"]})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_DIVERGENCE)

    def test_detector_group_absent_is_a_divergence(self):
        detector = self.write_detector([["u.R", "other_cols", 1, "alpha"]])
        spec = self.write_spec({"k_fields": ["alpha"]})
        bindings = self.write_bindings(
            self.simple_binding(waived_detector_groups=["other_cols"]))
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_DIVERGENCE)


class TestGateRefusesVacuousPass(GateHarness):
    """Every case here returned 0 with 'AGREE' printed before the rewrite."""

    def test_empty_detector_file_cannot_pass(self):
        detector = self.write_detector([], header=False)
        spec = self.write_spec({})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_detector_silent_about_this_source_file_cannot_pass(self):
        detector = self.write_detector([["elsewhere.R", "g_cols", 1, "alpha"]])
        spec = self.write_spec({"k_fields": ["alpha"]})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_pair_empty_on_both_sides_cannot_pass(self):
        detector = self.write_detector([["u.R", "present_cols", 1, "alpha"]])
        spec = self.write_spec({})
        bindings = self.write_bindings(
            self.simple_binding(group="absent_cols", constant="absent_fields",
                                waived_detector_groups=["present_cols"]))
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_uncompared_spec_vector_cannot_pass(self):
        """An uncompared name vector is precisely the run-2 defect."""
        detector = self.write_detector([["u.R", "g_cols", 1, "alpha"]])
        spec = self.write_spec({"k_fields": ["alpha"], "orphan_fields": ["x"]})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_uncompared_detector_group_cannot_pass(self):
        detector = self.write_detector([
            ["u.R", "g_cols", 1, "alpha"],
            ["u.R", "unbound_cols", 1, "zeta"],
        ])
        spec = self.write_spec({"k_fields": ["alpha"]})
        bindings = self.write_bindings(self.simple_binding())
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_explicit_waiver_allows_a_pass(self):
        detector = self.write_detector([
            ["u.R", "g_cols", 1, "alpha"],
            ["u.R", "unbound_cols", 1, "zeta"],
        ])
        spec = self.write_spec({"k_fields": ["alpha"], "orphan_fields": ["x"]})
        bindings = self.write_bindings(self.simple_binding(
            waived_detector_groups=["unbound_cols"],
            waived_spec_constants=["orphan_fields"]))
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_AGREE)

    def test_missing_bindings_file_cannot_pass(self):
        detector = self.write_detector([["u.R", "g_cols", 1, "alpha"]])
        spec = self.write_spec({"k_fields": ["alpha"]})
        self.assertEqual(
            self.run_gate(detector, spec, self.tmp / "does-not-exist.json"),
            EXIT_CANNOT_RUN)

    def test_empty_bindings_cannot_pass(self):
        detector = self.write_detector([["u.R", "g_cols", 1, "alpha"]])
        spec = self.write_spec({"k_fields": ["alpha"]})
        bindings = self.write_bindings([])
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_unknown_spec_unit_cannot_pass(self):
        detector = self.write_detector([["u.R", "g_cols", 1, "alpha"]])
        spec = self.write_spec({"k_fields": ["alpha"]}, unit="U01")
        bindings = self.write_bindings(self.simple_binding(unit="U99"))
        self.assertEqual(self.run_gate(detector, spec, bindings), EXIT_CANNOT_RUN)

    def test_shipped_bindings_stub_is_empty(self):
        """The kit must not ship a previous run's bindings as this run's gate."""
        stub = json.loads(
            (ROOT / "ocm-kit" / "contracts" / "detector_spec_bindings.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(stub["bindings"], [])
        self.assertIsNone(stub["run_id"])


class TestShippedContractsCarryNoPreviousRun(unittest.TestCase):
    """The kit's README promises it ships no previous run's answers."""

    def test_alias_map_is_empty(self):
        doc = json.loads((ROOT / "ocm-kit" / "contracts" / "alias_map.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(doc["entries"], [])
        self.assertIsNone(doc["run_id"])

    def test_run_params_is_empty(self):
        doc = json.loads((ROOT / "ocm-kit" / "contracts" / "run_params.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(doc["invoked_analyses"], {})
        self.assertIsNone(doc["run_id"])

    def test_provenance_tags_split_real_from_synthetic(self):
        """lessons finding 3: the two observation labels must never be one."""
        schema = json.loads(
            (ROOT / "ocm-kit" / "contracts" / "schemas" / "neutral_spec_schema.json")
            .read_text(encoding="utf-8"))
        text = json.dumps(schema)
        self.assertIn("observed_in_real_input", text)
        self.assertIn("observed_in_synthetic_input", text)
        self.assertNotIn('"observed_in_file"', text)

    def test_source_specific_scripts_are_marked_as_examples(self):
        """A run's own script must not sit unmarked among the general tools."""
        examples = ROOT / "ocm-kit" / "tools" / "examples"
        scripts = sorted(p for p in examples.glob("*.py"))
        self.assertTrue(scripts, "expected run-2 scripts kept as worked shapes")
        for path in scripts:
            head = path.read_text(encoding="utf-8")[:1200]
            self.assertIn("EXAMPLE ONLY", head, "%s lacks its EXAMPLE ONLY header" % path.name)

    def test_target_directives_ships_as_a_template(self):
        """The kit must not ship one run's directives as the next run's orders.

        A blanket "this file may mention run 2" exemption cannot distinguish
        prose explaining a removal from the directives themselves -- the first
        version of this test granted that exemption and then passed happily
        with run 2's Java/Swing directives restored. So this asserts a
        STRUCTURAL property instead: the kit's copy declares itself a template
        and names no concrete deliverable. A filled-in directives file always
        names one; a template never does.
        """
        path = ROOT / "ocm-kit" / "contracts" / "target_directives.md"
        text = path.read_text(encoding="utf-8")
        first_heading = next(l for l in text.splitlines() if l.startswith("#"))
        self.assertIn("TEMPLATE", first_heading,
                      "the kit's target_directives.md must declare itself a template")
        for concrete in ("Project name:", "Root package:", "Declared language level:"):
            self.assertNotIn(concrete, text,
                             "%r names a concrete deliverable; that belongs in a "
                             "run directory, not in the kit" % concrete)

    def test_no_tool_hard_codes_a_previous_run(self):
        leaked = ("kobra_numeric_cols", "bsv_loan_overview", "RSD-KOBRA",
                  "RSD-DECISION", "yield_curve_diagnostic", "swap_npv_history",
                  "ocm-hedging", "org.eclipse.jdt")
        offenders = []
        # contracts/*.md is scanned too: target_directives.md shipped run 2's
        # directives verbatim -- an Eclipse Java/Swing project named
        # ocm-hedging -- and this test's first version globbed only tools/, so
        # it missed the one file whose entire purpose is to be obeyed.
        candidates = (sorted((ROOT / "ocm-kit" / "tools").glob("*"))
                      + sorted((ROOT / "ocm-kit" / "contracts").glob("*.md")))
        for path in candidates:
            if path.suffix not in {".py", ".R", ".md"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in leaked:
                # The gate's docstring discusses run 2 by name; that is prose,
                # not a hard-coded identifier driving a comparison.
                # Prose that NAMES a previous run while explaining why its
                # content was removed is the opposite of a leak. Only files
                # that would drive behaviour are held to the literal check.
                narrates = path.name in {"check_detector_vs_spec.py",
                                         "target_directives.md",
                                         "canonicalisation_contract.md",
                                         "controller_flow.md"}
                if token in text and not narrates:
                    offenders.append("%s: %s" % (path.name, token))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()


class TestCompareExitContract(GateHarness):
    """COMPARE must not report agreement it did not establish.

    The tool originally had no sys.exit at all, so it returned 0 whatever it
    found -- including input lists that the canonicalisation contract says make
    two checkpoint files incomparable, which it printed and then passed anyway.
    """

    COMPARE = ROOT / "ocm-kit" / "tools" / "compare_checkpoints.py"

    def checkpoint(self, name, side, digest, inputs):
        path = self.tmp / name
        path.write_text(json.dumps({
            "run_id": "t", "side": side,
            "state": "OBSERVE_SOURCE" if side == "source" else "OBSERVE_TARGET",
            "canonicalisation": "dec9-half-even-v1",
            "emitted_utc": "2026-01-01T00:00:00Z",
            "inputs": inputs,
            "units": [{"unit": "U01", "objects": [{
                "name": "obj", "kind": "frame", "rows": 1, "cols": 1,
                "colnames": ["a"],
                "canonical_order": [{"column": "a", "direction": "asc"}],
                "digest": {"algorithm": "SHA-256",
                           "canonicalisation": "dec9-half-even-v1",
                           "value": digest},
                "coverage": {"row_count": 1, "field_count": 1, "null_count": 0,
                             "min": None, "max": None},
                "probes": []}]}],
        }), encoding="utf-8")
        return path

    def compare(self, src, tgt):
        import subprocess
        return subprocess.run(
            [sys.executable, str(self.COMPARE), str(src), str(tgt),
             str(self.tmp / "out.json")],
            capture_output=True, text=True).returncode

    IN_A = [{"name": "a.csv", "bytes": 1, "sha256": "a" * 64}]
    IN_AB = IN_A + [{"name": "b.json", "bytes": 2, "sha256": "b" * 64}]

    def test_same_inputs_and_same_digest_agree(self):
        src = self.checkpoint("s.json", "source", "c" * 64, self.IN_A)
        tgt = self.checkpoint("t.json", "target", "c" * 64, self.IN_A)
        self.assertEqual(self.compare(src, tgt), 0)

    def test_same_inputs_different_digest_is_a_divergence(self):
        src = self.checkpoint("s.json", "source", "c" * 64, self.IN_A)
        tgt = self.checkpoint("t.json", "target", "d" * 64, self.IN_A)
        self.assertEqual(self.compare(src, tgt), 1)

    def test_differing_input_lists_are_not_comparable(self):
        """Agreeing digests over different input lists establish nothing."""
        src = self.checkpoint("s.json", "source", "c" * 64, self.IN_A)
        tgt = self.checkpoint("t.json", "target", "c" * 64, self.IN_AB)
        self.assertEqual(self.compare(src, tgt), 2)
