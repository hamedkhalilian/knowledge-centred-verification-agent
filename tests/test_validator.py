import unittest

from kcv_agent import validate_ledger


def claim(
    claim_id: str,
    *,
    kind: str = "SOURCE",
    status: str = "VERIFIED",
    evidence_status: str = "PRIMARY",
    dependencies: list[str] | None = None,
    derivation_rule: str | None = None,
) -> dict:
    return {
        "id": claim_id,
        "statement": f"Statement for {claim_id}",
        "kind": kind,
        "status": status,
        "evidence_status": evidence_status,
        "dependencies": dependencies or [],
        "derivation_rule": derivation_rule,
    }


def rule_ids(ledger: dict) -> set[str]:
    return {finding.rule_id for finding in validate_ledger(ledger).findings}


class LedgerValidatorTests(unittest.TestCase):
    def test_valid_ledger_passes(self) -> None:
        ledger = {
            "claims": [
                claim("C-001"),
                claim(
                    "C-002",
                    kind="DERIVED",
                    evidence_status="NOT_REQUIRED",
                    dependencies=["C-001"],
                    derivation_rule="C-001 and the stated condition imply C-002.",
                ),
            ]
        }
        self.assertTrue(validate_ledger(ledger).ok)

    def test_duplicate_and_dangling_ids_are_detected(self) -> None:
        ledger = {
            "claims": [
                claim("C-001", dependencies=["C-404"]),
                claim("C-001"),
            ]
        }
        self.assertEqual(rule_ids(ledger), {"V-001", "V-003"})

    def test_cycle_and_illegal_status_are_detected(self) -> None:
        ledger = {
            "claims": [
                claim("C-001", dependencies=["C-002"]),
                claim(
                    "C-002",
                    status="VERIFIED",
                    evidence_status="NOT_RETRIEVED",
                    dependencies=["C-001"],
                ),
            ]
        }
        self.assertEqual(rule_ids(ledger), {"V-004", "V-005"})

    def test_derived_claim_requires_derivation_rule(self) -> None:
        ledger = {
            "claims": [
                claim("C-001"),
                claim(
                    "C-002",
                    kind="DERIVED",
                    evidence_status="NOT_REQUIRED",
                    dependencies=["C-001"],
                ),
            ]
        }
        self.assertEqual(rule_ids(ledger), {"V-008"})


if __name__ == "__main__":
    unittest.main()
