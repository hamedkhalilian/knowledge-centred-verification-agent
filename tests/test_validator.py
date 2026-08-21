import json
from pathlib import Path
import re
import unittest

from kcv_agent import validate_ledger
from kcv_agent.validator import (
    CLAIM_REQUIRED_FIELDS,
    CLAIM_STATUSES,
    CLAIM_TYPES,
    EVIDENCE_REQUIRED_FIELDS,
    EVIDENCE_RETRIEVAL_METHODS,
    EVIDENCE_STATUSES,
    RUN_REQUIRED_FIELDS,
    SOURCE_ACCESS_VALUES,
    SOURCE_KINDS,
    SOURCE_REQUIRED_FIELDS,
    STATUS_MATRIX,
)


ROOT = Path(__file__).resolve().parents[1]


def run() -> dict:
    return {
        "run_id": "R-TEST-01",
        "as_of_date": "2026-08-21",
        "document_manifest": [],
        "requested_output_formats": ["claim-ledger-json"],
        "strict_blind_audit_required": False,
        "prompt_version": "v2.2",
    }


def claim(
    claim_id: str,
    *,
    claim_type: str = "SOURCE",
    claim_status: str = "SUPPORTED",
    evidence_status: str = "PRIMARY_VERIFIED",
    depends_on: object | None = None,
    derivation_rule: str | None = None,
    qualification: str | None = None,
) -> dict:
    payload = {
        "claim_id": claim_id,
        "normalised_claim": f"Statement for {claim_id}",
        "claim_type": claim_type,
        "claim_status": claim_status,
        "evidence_status": evidence_status,
        "depends_on": [] if depends_on is None else depends_on,
    }
    if derivation_rule is not None:
        payload["derivation_rule"] = derivation_rule
    if qualification is not None:
        payload["qualification"] = qualification
    return payload


def ledger(*claims: dict) -> dict:
    payload = {
        "run": run(),
        "claims": list(claims),
        "sources": [
            {
                "source_id": "SRC-TEST",
                "kind": "internal",
                "identifier": "test-fixture",
                "title": "Validator test fixture",
                "version_label": "test",
                "version_date": "2026-08-21",
                "access": "INTERNAL",
                "locator": "tests/test_validator.py",
                "sufficient_for": ["validator_test"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "EV-TEST",
                "source_id": "SRC-TEST",
                "retrieved_at": "2026-08-21",
                "retrieval_method": "internal_source",
                "fragment": "test fixture",
                "extract": "Synthetic evidence for deterministic validator tests.",
                "supersession_checked": False,
                "superseded_by": [],
                "queries_attempted": [],
                "search_scope": None,
                "agent": "TEST",
                "prompt_version": "v2.2",
            }
        ],
        "edges": [
            {"from": "EV-TEST", "to": "SRC-TEST", "type": "RETRIEVED_FROM"}
        ],
    }
    for item in claims:
        if (
            item.get("claim_type") in {"SOURCE", "INTERPRETIVE", "DEFINITION"}
            and item.get("claim_status") in {"SUPPORTED", "SUPPORTED_CONDITIONAL"}
            and isinstance(item.get("claim_id"), str)
        ):
            payload["edges"].append(
                {
                    "from": item["claim_id"],
                    "to": "EV-TEST",
                    "type": "EVIDENCED_BY",
                    "stance": "AFFIRMS",
                }
            )
    return payload


def ledger_with_evidence(*, source_id: object = "SRC-001", edge_target: object = "SRC-001") -> dict:
    payload = ledger(claim("C-001"))
    payload["sources"] = [
        {
            "source_id": "SRC-001",
            "kind": "internal",
            "identifier": "test-source",
            "title": "Test source",
            "version_label": "test snapshot",
            "version_date": "2026-08-21",
            "access": "INTERNAL",
            "locator": "memory",
            "sufficient_for": ["test"],
        }
    ]
    payload["evidence"] = [
        {
            "evidence_id": "EV-001",
            "source_id": source_id,
            "retrieved_at": "2026-08-21",
            "retrieval_method": "internal_source",
            "fragment": "test fragment",
            "extract": "test extract",
            "supersession_checked": False,
            "superseded_by": [],
            "queries_attempted": [],
            "search_scope": None,
            "agent": "TEST",
            "prompt_version": "v2.2",
        }
    ]
    payload["edges"] = [
        {
            "from": "EV-001",
            "to": edge_target,
            "type": "RETRIEVED_FROM",
        },
        {
            "from": "C-001",
            "to": "EV-001",
            "type": "EVIDENCED_BY",
            "stance": "AFFIRMS",
        }
    ]
    return payload


def rule_ids(payload: dict) -> set[str]:
    return {finding.rule_id for finding in validate_ledger(payload).findings}


class LedgerValidatorTests(unittest.TestCase):
    def test_valid_ledger_passes(self) -> None:
        payload = ledger(
            claim("C-001"),
            claim(
                "C-002",
                claim_type="DERIVED",
                depends_on=["C-001"],
                derivation_rule="C-001 implies C-002.",
            ),
        )
        self.assertTrue(validate_ledger(payload).ok)

    def test_duplicate_and_dangling_ids_are_detected(self) -> None:
        payload = ledger(
            claim("C-001", depends_on=["C-404"]),
            claim("C-001"),
        )
        self.assertEqual(rule_ids(payload), {"V-001", "V-003"})

    def test_cycle_and_illegal_status_are_detected(self) -> None:
        payload = ledger(
            claim("C-001", depends_on=["C-002"]),
            claim(
                "C-002",
                claim_status="SUPPORTED",
                evidence_status="NOT_RETRIEVED",
                depends_on=["C-001"],
            ),
        )
        self.assertEqual(rule_ids(payload), {"V-004", "V-005"})

    def test_flag_cell_requires_qualification(self) -> None:
        payload = ledger(
            claim(
                "C-001",
                claim_status="SUPPORTED_CONDITIONAL",
                evidence_status="SECONDARY_ONLY",
            )
        )
        self.assertEqual(rule_ids(payload), {"V-024"})

    def test_qualified_flag_cell_passes(self) -> None:
        payload = ledger(
            claim(
                "C-001",
                claim_status="SUPPORTED_CONDITIONAL",
                evidence_status="SECONDARY_ONLY",
                qualification="Working position based on secondary material only.",
            )
        )
        self.assertTrue(validate_ledger(payload).ok)

    def test_derived_claim_requires_rule_and_premise(self) -> None:
        payload = ledger(
            claim("C-001", claim_type="DERIVED", derivation_rule="Non-empty rule.")
        )
        self.assertEqual(rule_ids(payload), {"V-008"})

    def test_supported_derived_claim_cannot_outrank_premise(self) -> None:
        payload = ledger(
            claim(
                "C-001",
                claim_status="UNESTABLISHED",
                evidence_status="NOT_RETRIEVED",
            ),
            claim(
                "C-002",
                claim_type="DERIVED",
                depends_on=["C-001"],
                derivation_rule="C-001 implies C-002.",
            ),
        )
        self.assertEqual(rule_ids(payload), {"V-006D"})

    def test_conditional_derived_claim_accepts_conditional_premise(self) -> None:
        payload = ledger(
            claim(
                "C-001",
                claim_status="SUPPORTED_CONDITIONAL",
                evidence_status="SECONDARY_ONLY",
                qualification="Premise is conditional and secondary-only.",
            ),
            claim(
                "C-002",
                claim_type="DERIVED",
                claim_status="SUPPORTED_CONDITIONAL",
                evidence_status="SECONDARY_ONLY",
                depends_on=["C-001"],
                derivation_rule="C-001 implies C-002 under the same condition.",
                qualification="Conclusion preserves the premise qualification.",
            ),
        )
        self.assertTrue(validate_ledger(payload).ok)

    def test_missing_or_non_string_claim_id_is_blocking(self) -> None:
        missing = claim("C-001")
        missing.pop("claim_id")
        non_string = claim("C-002")
        non_string["claim_id"] = 2
        self.assertIn("V-000", rule_ids(ledger(missing)))
        self.assertIn("V-000", rule_ids(ledger(non_string)))

    def test_string_dependency_field_is_not_silently_ignored(self) -> None:
        payload = ledger(claim("C-001", depends_on="C-002"), claim("C-002"))
        self.assertEqual(rule_ids(payload), {"V-000"})

    def test_empty_ledger_is_blocking(self) -> None:
        self.assertEqual(rule_ids({"run": run(), "claims": []}), {"V-000"})

    def test_positive_evidence_requires_existing_source_and_matching_edge(self) -> None:
        self.assertTrue(validate_ledger(ledger_with_evidence()).ok)
        self.assertIn(
            "V-003",
            rule_ids(ledger_with_evidence(source_id="SRC-DOES-NOT-EXIST")),
        )
        self.assertIn(
            "V-003",
            rule_ids(ledger_with_evidence(edge_target="SRC-DOES-NOT-EXIST")),
        )

    def test_supported_external_claim_requires_positive_claim_evidence(self) -> None:
        missing_edge = ledger_with_evidence()
        missing_edge["edges"] = [
            edge for edge in missing_edge["edges"]
            if edge["type"] != "EVIDENCED_BY"
        ]
        self.assertIn("V-006", rule_ids(missing_edge))

        silent_only = ledger_with_evidence()
        evidenced_by = next(
            edge for edge in silent_only["edges"]
            if edge["type"] == "EVIDENCED_BY"
        )
        evidenced_by["stance"] = "SILENT"
        self.assertIn("V-006", rule_ids(silent_only))

    def test_negative_retrieval_must_not_claim_a_source_or_edge(self) -> None:
        payload = ledger_with_evidence()
        payload["claims"][0]["claim_status"] = "UNESTABLISHED"
        payload["claims"][0]["evidence_status"] = "NOT_RETRIEVED"
        payload["evidence"][0]["retrieval_method"] = "none"
        self.assertIn("V-003", rule_ids(payload))

        payload["evidence"][0]["source_id"] = None
        payload["edges"] = []
        self.assertTrue(validate_ledger(payload).ok)

    def test_evidenced_by_edges_require_existing_typed_endpoints(self) -> None:
        payload = ledger_with_evidence()
        payload["edges"].append(
            {
                "from": "C-001",
                "to": "EV-001",
                "type": "EVIDENCED_BY",
                "stance": "AFFIRMS",
            }
        )
        self.assertTrue(validate_ledger(payload).ok)

        payload["edges"][-1]["to"] = "EV-MISSING"
        self.assertIn("V-003", rule_ids(payload))
        payload["edges"][-1]["to"] = "EV-001"
        payload["edges"][-1]["from"] = "C-MISSING"
        self.assertIn("V-003", rule_ids(payload))
        payload["edges"][-1]["from"] = "C-001"
        payload["edges"][-1]["stance"] = "GLOBAL_AFFIRMATION"
        self.assertIn("V-000", rule_ids(payload))

    def test_duplicate_source_and_evidence_ids_are_blocking(self) -> None:
        duplicate_source = ledger_with_evidence()
        duplicate_source["sources"].append({"source_id": "SRC-001"})
        self.assertIn("V-000", rule_ids(duplicate_source))

        duplicate_evidence = ledger_with_evidence()
        duplicate_evidence["evidence"].append(
            {
                "evidence_id": "EV-001",
                "source_id": "SRC-MISSING",
                "retrieval_method": "internal_source",
            }
        )
        self.assertIn("V-000", rule_ids(duplicate_evidence))
        self.assertIn("V-003", rule_ids(duplicate_evidence))

    def test_negative_retrieval_edges_require_silent_stance(self) -> None:
        payload = ledger_with_evidence()
        payload["claims"][0]["claim_status"] = "UNESTABLISHED"
        payload["claims"][0]["evidence_status"] = "NOT_RETRIEVED"
        payload["evidence"][0]["retrieval_method"] = "none"
        payload["evidence"][0]["source_id"] = None
        payload["edges"] = [
            {
                "from": "C-001",
                "to": "EV-001",
                "type": "EVIDENCED_BY",
                "stance": "AFFIRMS",
            }
        ]
        self.assertIn("V-025", rule_ids(payload))

        payload["edges"][0]["stance"] = "SILENT"
        self.assertTrue(validate_ledger(payload).ok)

    def test_evidence_must_not_store_global_stance(self) -> None:
        payload = ledger_with_evidence()
        payload["evidence"][0]["stance"] = "AFFIRMS"
        self.assertIn("V-025", rule_ids(payload))

    def test_non_scalar_evidence_enums_are_blocking_not_crashing(self) -> None:
        bad_method = ledger_with_evidence()
        bad_method["evidence"][0]["retrieval_method"] = ["internal_source"]
        self.assertIn("V-000", rule_ids(bad_method))

        bad_stance = ledger_with_evidence()
        bad_stance["edges"].append(
            {
                "from": "C-001",
                "to": "EV-001",
                "type": "EVIDENCED_BY",
                "stance": {"value": "AFFIRMS"},
            }
        )
        self.assertIn("V-000", rule_ids(bad_stance))

    def test_source_structure_and_vocabularies_are_runtime_validated(self) -> None:
        bad_kind = ledger_with_evidence()
        bad_kind["sources"][0]["kind"] = ["internal"]
        self.assertIn("V-000", rule_ids(bad_kind))

        bad_access = ledger_with_evidence()
        bad_access["sources"][0]["access"] = {"value": "INTERNAL"}
        self.assertIn("V-000", rule_ids(bad_access))

        missing_title = ledger_with_evidence()
        missing_title["sources"][0].pop("title")
        self.assertIn("V-000", rule_ids(missing_title))

        empty_sufficiency = ledger_with_evidence()
        empty_sufficiency["sources"][0]["sufficient_for"] = [""]
        self.assertIn("V-000", rule_ids(empty_sufficiency))

    def test_evidence_required_structure_is_runtime_validated(self) -> None:
        payload = ledger_with_evidence()
        payload["evidence"][0].pop("retrieved_at")
        self.assertIn("V-000", rule_ids(payload))

    def test_dates_require_rfc3339_full_date_shape(self) -> None:
        compact_source = ledger_with_evidence()
        compact_source["sources"][0]["version_date"] = "20260821"
        self.assertIn("V-000", rule_ids(compact_source))

        week_date_evidence = ledger_with_evidence()
        week_date_evidence["evidence"][0]["retrieved_at"] = "2026-W34-5"
        self.assertIn("V-000", rule_ids(week_date_evidence))

    def test_non_object_ledger_root_is_blocking_not_crashing(self) -> None:
        self.assertEqual(
            {finding.rule_id for finding in validate_ledger([]).findings},
            {"V-000"},
        )

    def test_run_required_fields_are_enforced(self) -> None:
        payload = ledger(claim("C-001"))
        payload["run"] = {"run_id": "R-INCOMPLETE"}
        self.assertEqual(rule_ids(payload), {"V-000"})

    def test_assumption_is_not_a_claim_type(self) -> None:
        payload = ledger(claim("C-001", claim_type="ASSUMPTION"))
        self.assertEqual(rule_ids(payload), {"V-000"})

    def test_deep_dependency_chain_does_not_recurse(self) -> None:
        claims = []
        for index in range(3000):
            claim_id = f"C-{index:04d}"
            dependency = [] if index == 0 else [f"C-{index - 1:04d}"]
            claims.append(claim(claim_id, depends_on=dependency))
        self.assertTrue(validate_ledger(ledger(*claims)).ok)

    def test_example_ledger_passes(self) -> None:
        payload = json.loads(
            (ROOT / "examples/498-bgb/claim-ledger.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(validate_ledger(payload).ok)

    def test_schema_vocabularies_match_validator_constants(self) -> None:
        claim_schema = json.loads(
            (ROOT / "schemas/claim.schema.json").read_text(encoding="utf-8")
        )
        run_schema = json.loads(
            (ROOT / "schemas/run.schema.json").read_text(encoding="utf-8")
        )
        finding_schema = json.loads(
            (ROOT / "schemas/finding.schema.json").read_text(encoding="utf-8")
        )
        source_schema = json.loads(
            (ROOT / "schemas/source.schema.json").read_text(encoding="utf-8")
        )
        evidence_schema = json.loads(
            (ROOT / "schemas/evidence.schema.json").read_text(encoding="utf-8")
        )

        properties = claim_schema["properties"]
        self.assertEqual(set(properties["claim_type"]["enum"]), CLAIM_TYPES)
        self.assertEqual(set(properties["claim_status"]["enum"]), CLAIM_STATUSES)
        self.assertEqual(
            set(properties["evidence_status"]["enum"]), EVIDENCE_STATUSES
        )
        self.assertEqual(set(claim_schema["required"]), CLAIM_REQUIRED_FIELDS)
        self.assertEqual(set(run_schema["required"]), RUN_REQUIRED_FIELDS)
        self.assertEqual(
            set(source_schema["properties"]["kind"]["enum"]), SOURCE_KINDS
        )
        self.assertEqual(
            set(source_schema["properties"]["access"]["enum"]),
            SOURCE_ACCESS_VALUES,
        )
        self.assertEqual(set(source_schema["required"]), SOURCE_REQUIRED_FIELDS)
        self.assertEqual(
            set(evidence_schema["properties"]["retrieval_method"]["enum"]),
            EVIDENCE_RETRIEVAL_METHODS,
        )
        self.assertEqual(set(evidence_schema["required"]), EVIDENCE_REQUIRED_FIELDS)
        self.assertIsNotNone(
            re.fullmatch(finding_schema["properties"]["rule_id"]["pattern"], "V-006D")
        )

    def test_status_matrix_is_exact_protocol_transcription(self) -> None:
        columns = [
            "PRIMARY_VERIFIED",
            "AUTHORITATIVE_SECONDARY",
            "SECONDARY_ONLY",
            "LICENSE_REQUIRED",
            "NOT_RETRIEVED",
            "SOURCE_CONFLICT",
        ]
        rows = {
            "SUPPORTED": ["OK", "OK", "FLAG", None, None, None],
            "SUPPORTED_CONDITIONAL": ["OK", "OK", "FLAG", None, None, None],
            "UNESTABLISHED": ["FLAG", "FLAG", "OK", "OK", "OK", None],
            "UNSUPPORTED": ["OK", "OK", "FLAG", None, None, None],
            "CONTRADICTED": ["OK", "OK", "FLAG", None, None, None],
            "OUTDATED": ["OK", "OK", "FLAG", None, None, None],
            "UNRESOLVED": ["OK", "OK", "OK", None, None, "OK"],
            "PENDING": [None, None, None, "OK", "OK", "OK"],
        }
        actual = {
            claim_status: [STATUS_MATRIX[claim_status].get(column) for column in columns]
            for claim_status in rows
        }
        self.assertEqual(actual, rows)


if __name__ == "__main__":
    unittest.main()
