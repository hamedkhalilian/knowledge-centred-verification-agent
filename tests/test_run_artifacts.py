from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "254-hgb-bausparkasse"
SCHEMA_DIR = ROOT / "schemas"


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def assert_valid(instance: object, schema_name: str) -> None:
    schema = load_json(SCHEMA_DIR / schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    assert not errors, "\n".join(
        f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in errors
    )


def test_run_claims_findings_and_manifest_match_their_schemas() -> None:
    ledger = load_json(RUN_DIR / "claim-ledger.json")
    findings = load_json(RUN_DIR / "findings.json")
    manifest = load_json(RUN_DIR / "artifact_manifest.json")

    assert_valid(ledger["run"], "run.schema.json")
    for claim in ledger["claims"]:
        assert_valid(claim, "claim.schema.json")
    for source in ledger["sources"]:
        assert_valid(source, "source.schema.json")
    for evidence in ledger["evidence"]:
        assert_valid(evidence, "evidence.schema.json")
    for finding in findings["findings"]:
        assert_valid(finding, "protocol-finding.schema.json")
    assert_valid(manifest, "artifact-manifest.schema.json")


def test_manifest_verifies_every_produced_artifact() -> None:
    manifest = load_json(RUN_DIR / "artifact_manifest.json")
    produced = {
        artifact["name"]: artifact
        for artifact in manifest["artifacts"]
        if artifact["status"] == "PRODUCED"
    }

    for artifact in produced.values():
        path = ROOT / artifact["path_or_reference"]
        assert path.is_file(), f"Missing produced artifact: {path}"
        assert path.stat().st_size > 0, f"Empty produced artifact: {path}"
        assert artifact["non_empty_verified"] is True

    ledger = load_json(RUN_DIR / "claim-ledger.json")
    assert set(ledger["run"]["requested_output_formats"]) <= set(produced)


def test_gate_states_do_not_overclaim_missing_artifacts() -> None:
    ledger = load_json(RUN_DIR / "claim-ledger.json")
    manifest = load_json(RUN_DIR / "artifact_manifest.json")
    gates = ledger["run"]["gates"]
    by_name = {artifact["name"]: artifact for artifact in manifest["artifacts"]}

    assert by_name["rendered_locations.json"]["status"] == "NOT_PRODUCED"
    for gate in ("G-02", "G-04", "G-06", "G-07"):
        assert gates[gate] == "NOT_EVALUATED"
    assert gates["G-13"] == "NOT_EVALUATED"

    assert any(
        artifact["status"] in {"NOT_PRODUCED", "FAILED"}
        for artifact in manifest["artifacts"]
    )
    assert gates["G-15"] == "FAIL"

    protocol_minimum = {
        "artifact_manifest.json",
        "master_claim_ledger.json",
        "assumptions.json",
        "decisions.json",
        "quantities.json",
        "dependency_graph.json",
        "rendered_locations.json",
        "source_register.json",
        "evidence_register.json",
        "currency_log.json",
        "requires_licensed_source.json",
        "findings.json",
        "audit_report.json",
        "entailment_report.json",
        "mechanical_checks.json",
        "gate_report.json",
        "change_log.json",
        "regenerated_spans.json",
        "unresolved_human_actions.json",
    }
    assert protocol_minimum <= set(by_name)


def test_issue_provenance_and_closure_actions_are_explicit() -> None:
    ledger = load_json(RUN_DIR / "claim-ledger.json")
    source_manifest = load_json(RUN_DIR / "source-manifest.json")
    report = (RUN_DIR / "report.md").read_text(encoding="utf-8")
    release_summary = (RUN_DIR / "release-summary.md").read_text(encoding="utf-8")

    issue_source = next(
        source for source in source_manifest["sources"]
        if source["source_id"] == "SRC-INT-003"
    )
    issue_evidence = next(
        evidence for evidence in ledger["evidence"]
        if evidence["evidence_id"] == "EV-0003"
    )

    assert issue_source["kind"] == "internal"
    assert issue_source["access"] == "INTERNAL"
    assert issue_source["status"] == "RETRIEVED"
    assert "supplied" in issue_source["provenance_note"].lower()
    assert issue_evidence["retrieval_method"] == "internal_source"
    ledger_source = next(
        source for source in ledger["sources"]
        if source["source_id"] == "SRC-INT-003"
    )
    assert ledger_source["kind"] == issue_source["kind"]
    assert ledger_source["access"] == issue_source["access"]
    assert "supplied" in ledger_source["provenance_note"].lower()
    assert "D-0001" in report
    assert "D-0001" in release_summary


def test_rejected_review_finding_has_persisted_internal_evidence() -> None:
    ledger = load_json(RUN_DIR / "claim-ledger.json")
    source_manifest = load_json(RUN_DIR / "source-manifest.json")
    findings = load_json(RUN_DIR / "findings.json")

    ledger_sources = {source["source_id"]: source for source in ledger["sources"]}
    manifest_sources = {
        source["source_id"]: source for source in source_manifest["sources"]
    }
    evidence = {
        item["evidence_id"]: item for item in ledger["evidence"]
    }

    for source_id in ("SRC-INT-004", "SRC-INT-005"):
        assert ledger_sources[source_id]["kind"] == "internal"
        assert ledger_sources[source_id]["access"] == "INTERNAL"
        assert manifest_sources[source_id]["status"] == "RETRIEVED"
        assert "connected github" in (
            ledger_sources[source_id]["provenance_note"].lower()
        )

    assert evidence["EV-0004"]["source_id"] == "SRC-INT-004"
    assert evidence["EV-0004"]["retrieval_method"] == "internal_source"
    assert "not independently" in evidence["EV-0004"]["extract"].lower()
    assert evidence["EV-0005"]["source_id"] == "SRC-INT-005"
    assert evidence["EV-0005"]["retrieval_method"] == "internal_source"
    assert "resolved and executed" in evidence["EV-0005"]["extract"].lower()

    action_finding = next(
        finding for finding in findings["findings"]
        if finding["finding_id"] == "F-254-014"
    )
    assert action_finding["resolution"] == "REJECTED"
    assert "EV-0005" in action_finding["resolution_reason"]


def test_evidenced_by_edges_remain_claim_scoped() -> None:
    ledger = load_json(RUN_DIR / "claim-ledger.json")
    claim_ids = {claim["claim_id"] for claim in ledger["claims"]}

    for edge in ledger["edges"]:
        if edge["type"] == "EVIDENCED_BY":
            assert edge["from"] in claim_ids


def test_actionable_findings_require_exactly_one_remediation_class() -> None:
    findings = load_json(RUN_DIR / "findings.json")["findings"]
    schema = load_json(SCHEMA_DIR / "protocol-finding.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    actionable = dict(next(
        finding for finding in findings if finding["resolution"] == "ACCEPTED"
    ))
    actionable.pop("remediation_class")
    assert list(validator.iter_errors(actionable))

    rejected = dict(next(
        finding for finding in findings if finding["resolution"] == "REJECTED"
    ))
    rejected["remediation_class"] = "AUTO_FIXABLE"
    assert list(validator.iter_errors(rejected))


def test_each_use_case_has_a_separate_eight_dimension_analysis() -> None:
    report = (RUN_DIR / "report.md").read_text(encoding="utf-8")
    headings = (
        "### 5.1 Fixed-rate Bauspardarlehen portfolio + standard IRS",
        "### 5.2 Single Bauspardarlehen + coupon-matching off-market swap",
        "### 5.3 Customer optionality + swaption or option strategy",
        "### 5.4 Macro/portfolio hedge for collective Bauspar business",
    )
    dimensions = (
        "Economic risk reduction",
        "Legal eligibility",
        "Designation/documentation",
        "Effectiveness",
        "Risk inventory",
        "Accounting",
        "Prudential/IRRBB",
        "Assumptions/decisions",
    )

    sections = report.split("### 5.")
    assert len(sections) == 5
    for heading in headings:
        assert heading in report
    for section in sections[1:]:
        for dimension in dimensions:
            assert f"| {dimension} |" in section
