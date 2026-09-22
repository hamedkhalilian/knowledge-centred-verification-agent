"""Tests for the OCM R source detector (ocm-kit/tools/r_source_detector.R).

Skipped when R is not installed. The detector is the mandatory PROFILE
artifact: the R3 gate compares its output against the spec, so a detector that
halts -- or that silently reports nothing -- disarms the gate downstream.
"""
import csv
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = ROOT / "ocm-kit" / "tools" / "r_source_detector.R"
RSCRIPT = shutil.which("Rscript")


@unittest.skipIf(RSCRIPT is None, "Rscript not installed")
class TestRSourceDetector(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()

    def detect(self, probes=None):
        cmd = [RSCRIPT, str(DETECTOR), "--r-dir", str(self.src), "--out-dir", str(self.out)]
        if probes is not None:
            cmd += ["--probes", str(probes)]
        return subprocess.run(cmd, capture_output=True, text=True)

    def findings(self):
        path = self.out / "r_source_findings.csv"
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def test_survives_a_function_with_a_non_defaulted_parameter(self):
        """A formal with no default holds R's empty symbol.

        Binding it to a local and touching the local raises "argument is
        missing", which halted the detector on nearly any real R file. The
        emptiness has to be tested in place, before the binding.
        """
        (self.src / "plain.R").write_text(
            "add <- function(a, b = 2) a + b\n"
            "scale_all <- function(values, factor) values * factor\n",
            encoding="utf-8")
        result = self.detect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.out / "r_source_contract.json").exists())

    def test_captures_defaults_it_can_see(self):
        (self.src / "defs.R").write_text(
            "f <- function(required, label = \"total\", n = 3) NULL\n", encoding="utf-8")
        self.assertEqual(self.detect().returncode, 0)
        with (self.out / "r_source_function_defaults.csv").open(newline="", encoding="utf-8") as fh:
            captured = {r["parameter"]: r["default_value"] for r in csv.DictReader(fh)}
        self.assertEqual(captured.get("label"), "total")
        self.assertEqual(captured.get("n"), "3")
        self.assertNotIn("required", captured)

    def test_absence_of_probes_is_reported_not_implied(self):
        """Silence must be declared. 'No findings' is not 'nothing to find'."""
        (self.src / "plain.R").write_text("f <- function(x) x\n", encoding="utf-8")
        self.assertEqual(self.detect().returncode, 0)
        self.assertIn("RSD-NO-PROBES", {f["code"] for f in self.findings()})

    def test_declared_text_probe_fires_only_when_every_pattern_matches(self):
        (self.src / "logic.R").write_text(
            "decide <- function(spread, threshold) spread > threshold\n", encoding="utf-8")
        probes = self.tmp / "probes.csv"
        probes.write_text(
            "kind,code,object,field,pattern,message\n"
            "text,P-BOTH,,,spread,both patterns present\n"
            "text,P-BOTH,,,threshold,both patterns present\n"
            "text,P-PARTIAL,,,spread,should not fire\n"
            "text,P-PARTIAL,,,absent_token_xyz,should not fire\n",
            encoding="utf-8")
        self.assertEqual(self.detect(probes=probes).returncode, 0)
        codes = {f["code"] for f in self.findings()}
        self.assertIn("P-BOTH", codes)
        self.assertNotIn("P-PARTIAL", codes)

    def test_unevaluable_anchor_probe_says_so(self):
        """A declared probe that could not be checked must not vanish."""
        (self.src / "plain.R").write_text("f <- function(x) x\n", encoding="utf-8")
        probes = self.tmp / "probes.csv"
        probes.write_text(
            "kind,code,object,field,pattern,message\n"
            "anchor,P-ANCHOR,some_object,some_field,,\n", encoding="utf-8")
        self.assertEqual(self.detect(probes=probes).returncode, 0)
        self.assertIn("RSD-ANCHOR-NO-LAYOUT", {f["code"] for f in self.findings()})


if __name__ == "__main__":
    unittest.main()
