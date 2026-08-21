"""Deterministic Claim Ledger validators.

The protocol in ``prompts/master_prompt_v2.2.md`` is authoritative. This module
implements only checks that can be evaluated mechanically from the currently
modelled Run and Claim objects; semantic truth and source adequacy remain
separate review concerns.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
import re
from typing import Any, Iterator

from .models import Finding, ValidationResult


CLAIM_TYPES = frozenset({"SOURCE", "DERIVED", "INTERPRETIVE", "DEFINITION"})
CLAIM_STATUSES = frozenset(
    {
        "PENDING",
        "SUPPORTED",
        "SUPPORTED_CONDITIONAL",
        "UNESTABLISHED",
        "UNSUPPORTED",
        "CONTRADICTED",
        "OUTDATED",
        "UNRESOLVED",
    }
)
EVIDENCE_STATUSES = frozenset(
    {
        "PRIMARY_VERIFIED",
        "AUTHORITATIVE_SECONDARY",
        "SECONDARY_ONLY",
        "LICENSE_REQUIRED",
        "NOT_RETRIEVED",
        "SOURCE_CONFLICT",
    }
)

# Exact transcription of the normative §3.5 matrix. Missing cells are illegal.
# FLAG cells are legal only when the Claim carries an explicit qualification.
STATUS_MATRIX: dict[str, dict[str, str]] = {
    "SUPPORTED": {
        "PRIMARY_VERIFIED": "OK",
        "AUTHORITATIVE_SECONDARY": "OK",
        "SECONDARY_ONLY": "FLAG",
    },
    "SUPPORTED_CONDITIONAL": {
        "PRIMARY_VERIFIED": "OK",
        "AUTHORITATIVE_SECONDARY": "OK",
        "SECONDARY_ONLY": "FLAG",
    },
    "UNESTABLISHED": {
        "PRIMARY_VERIFIED": "FLAG",
        "AUTHORITATIVE_SECONDARY": "FLAG",
        "SECONDARY_ONLY": "OK",
        "LICENSE_REQUIRED": "OK",
        "NOT_RETRIEVED": "OK",
    },
    "UNSUPPORTED": {
        "PRIMARY_VERIFIED": "OK",
        "AUTHORITATIVE_SECONDARY": "OK",
        "SECONDARY_ONLY": "FLAG",
    },
    "CONTRADICTED": {
        "PRIMARY_VERIFIED": "OK",
        "AUTHORITATIVE_SECONDARY": "OK",
        "SECONDARY_ONLY": "FLAG",
    },
    "OUTDATED": {
        "PRIMARY_VERIFIED": "OK",
        "AUTHORITATIVE_SECONDARY": "OK",
        "SECONDARY_ONLY": "FLAG",
    },
    "UNRESOLVED": {
        "PRIMARY_VERIFIED": "OK",
        "AUTHORITATIVE_SECONDARY": "OK",
        "SECONDARY_ONLY": "OK",
        "SOURCE_CONFLICT": "OK",
    },
    "PENDING": {
        "LICENSE_REQUIRED": "OK",
        "NOT_RETRIEVED": "OK",
        "SOURCE_CONFLICT": "OK",
    },
}

RUN_REQUIRED_FIELDS = frozenset(
    {
        "run_id",
        "as_of_date",
        "document_manifest",
        "requested_output_formats",
        "strict_blind_audit_required",
        "prompt_version",
    }
)
CLAIM_REQUIRED_FIELDS = frozenset(
    {
        "claim_id",
        "normalised_claim",
        "claim_type",
        "claim_status",
        "evidence_status",
        "depends_on",
    }
)
CLAIM_FIELDS = frozenset(
    {
        *CLAIM_REQUIRED_FIELDS,
        "class",
        "time_sensitive",
        "source_statement",
        "conditions",
        "decision_conditions",
        "blocked_by",
        "derivation_rule",
        "appears_in",
        "severity_if_wrong",
        "last_checked",
        "last_successfully_verified",
        "reopened",
        "qualification",
    }
)
CAPABILITY_FIELDS = frozenset(
    {
        "input_file_access",
        "external_retrieval",
        "code_execution",
        "file_output",
        "document_compile",
        "image_render",
        "isolated_audit_context",
    }
)
RUN_GATE_STATUSES = frozenset({"PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE"})
CLAIM_SEVERITIES = frozenset({"BLOCKING", "HIGH", "MEDIUM", "LOW"})
CLAIM_ID_PATTERN = re.compile(r"^C-?[A-Za-z0-9][A-Za-z0-9._-]*$")


class LedgerValidator:
    """Apply stable structural, graph, and state rules to a ledger mapping."""

    def validate(self, ledger: Mapping[str, Any]) -> ValidationResult:
        findings: list[Finding] = []
        self._validate_run(ledger.get("run"), findings)
        claims = self._claims(ledger, findings)
        if claims is None:
            return ValidationResult(tuple(findings))

        for index, claim in enumerate(claims):
            self._validate_claim_structure(claim, index, findings)

        ids = [
            claim["claim_id"]
            for claim in claims
            if isinstance(claim.get("claim_id"), str)
            and CLAIM_ID_PATTERN.fullmatch(claim["claim_id"])
        ]
        id_set = set(ids)
        by_id: dict[str, Mapping[str, Any]] = {}
        for claim in claims:
            claim_id = claim.get("claim_id")
            if isinstance(claim_id, str) and claim_id in id_set:
                by_id.setdefault(claim_id, claim)

        findings.extend(self._duplicate_ids(ids))
        findings.extend(self._dangling_dependencies(claims, id_set))
        findings.extend(self._dependency_cycles(claims, id_set))
        findings.extend(self._status_combinations(claims))
        findings.extend(self._derived_claims(claims, by_id))

        return ValidationResult(tuple(findings))

    @staticmethod
    def _validate_run(raw_run: Any, findings: list[Finding]) -> None:
        if not isinstance(raw_run, Mapping):
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", "Ledger field 'run' must be an object.")
            )
            return

        for field in sorted(RUN_REQUIRED_FIELDS - raw_run.keys()):
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", f"Run is missing required field '{field}'.")
            )

        if "run_id" in raw_run and not _non_empty_string(raw_run["run_id"]):
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", "Run field 'run_id' must be a non-empty string.")
            )
        if "as_of_date" in raw_run and not _iso_date(raw_run["as_of_date"]):
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", "Run field 'as_of_date' must be an ISO date.")
            )
        for field in ("document_manifest", "requested_output_formats"):
            if field in raw_run and not _string_list(raw_run[field]):
                findings.append(
                    Finding("V-000", "RELEASE_BLOCKING", f"Run field '{field}' must be a list of strings.")
                )
        if "strict_blind_audit_required" in raw_run and not isinstance(
            raw_run["strict_blind_audit_required"], bool
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    "Run field 'strict_blind_audit_required' must be boolean.",
                )
            )
        if "prompt_version" in raw_run and raw_run["prompt_version"] != "v2.2":
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", "Run field 'prompt_version' must equal 'v2.2'.")
            )
        for field in ("model_id", "inherited_from_run"):
            if field in raw_run and raw_run[field] is not None and not _non_empty_string(
                raw_run[field]
            ):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Run field '{field}' must be a non-empty string or null.",
                    )
                )
        capabilities = raw_run.get("capabilities")
        if capabilities is not None:
            if not isinstance(capabilities, Mapping):
                findings.append(
                    Finding("V-000", "RELEASE_BLOCKING", "Run field 'capabilities' must be an object.")
                )
            else:
                unknown = sorted(capabilities.keys() - CAPABILITY_FIELDS)
                for field in unknown:
                    findings.append(
                        Finding("V-000", "RELEASE_BLOCKING", f"Unknown capability field '{field}'.")
                    )
                for field, value in capabilities.items():
                    if field in CAPABILITY_FIELDS and not isinstance(value, bool):
                        findings.append(
                            Finding(
                                "V-000",
                                "RELEASE_BLOCKING",
                                f"Capability '{field}' must be boolean.",
                            )
                        )
        gates = raw_run.get("gates")
        if gates is not None:
            if not isinstance(gates, Mapping):
                findings.append(
                    Finding("V-000", "RELEASE_BLOCKING", "Run field 'gates' must be an object.")
                )
            else:
                for gate, status in gates.items():
                    if not _non_empty_string(gate) or status not in RUN_GATE_STATUSES:
                        findings.append(
                            Finding(
                                "V-000",
                                "RELEASE_BLOCKING",
                                f"Run gate {gate!r} has invalid status={status!s}.",
                            )
                        )

    @staticmethod
    def _claims(
        ledger: Mapping[str, Any], findings: list[Finding]
    ) -> list[Mapping[str, Any]] | None:
        raw_claims = ledger.get("claims")
        if not isinstance(raw_claims, Sequence) or isinstance(raw_claims, (str, bytes)):
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", "Ledger field 'claims' must be a list.")
            )
            return None
        if not raw_claims:
            findings.append(
                Finding("V-000", "RELEASE_BLOCKING", "Ledger field 'claims' must not be empty.")
            )

        claims: list[Mapping[str, Any]] = []
        for index, claim in enumerate(raw_claims):
            if not isinstance(claim, Mapping):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Claim at index {index} must be an object.",
                    )
                )
                continue
            claims.append(claim)
        return claims

    @staticmethod
    def _validate_claim_structure(
        claim: Mapping[str, Any], index: int, findings: list[Finding]
    ) -> None:
        claim_id = claim.get("claim_id")
        location = claim_id if isinstance(claim_id, str) else None

        for field in sorted(CLAIM_REQUIRED_FIELDS - claim.keys()):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim at index {index} is missing required field '{field}'.",
                    location,
                )
            )
        for field in sorted(claim.keys() - CLAIM_FIELDS):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim at index {index} has unknown field '{field}'.",
                    location,
                )
            )

        if "claim_id" in claim and (
            not isinstance(claim_id, str) or not CLAIM_ID_PATTERN.fullmatch(claim_id)
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim at index {index} has an invalid 'claim_id'.",
                    location,
                )
            )
        if "normalised_claim" in claim and not _non_empty_string(claim["normalised_claim"]):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} field 'normalised_claim' must be a non-empty string.",
                    location,
                )
            )
        if "claim_type" in claim and claim["claim_type"] not in CLAIM_TYPES:
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} has invalid claim_type={claim['claim_type']!s}.",
                    location,
                )
            )
        if "claim_status" in claim and claim["claim_status"] not in CLAIM_STATUSES:
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} has invalid claim_status={claim['claim_status']!s}.",
                    location,
                )
            )
        if "evidence_status" in claim and claim["evidence_status"] not in EVIDENCE_STATUSES:
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} has invalid evidence_status={claim['evidence_status']!s}.",
                    location,
                )
            )
        if "depends_on" in claim and not _claim_id_list(claim["depends_on"]):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} field 'depends_on' must be a unique list of Claim IDs.",
                    location,
                )
            )

        for field in ("conditions", "blocked_by", "appears_in", "class"):
            if field in claim and not _string_list(claim[field]):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Claim {claim_id!s} field '{field}' must be a list of strings.",
                        location,
                    )
                )
        if "decision_conditions" in claim and not _decision_conditions(
            claim["decision_conditions"]
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} field 'decision_conditions' is malformed.",
                    location,
                )
            )
        for field in ("last_checked", "last_successfully_verified"):
            if field in claim and claim[field] is not None and not _iso_date(claim[field]):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Claim {claim_id!s} field '{field}' must be an ISO date or null.",
                        location,
                    )
                )
        for field in ("time_sensitive", "reopened"):
            if field in claim and not isinstance(claim[field], bool):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Claim {claim_id!s} field '{field}' must be boolean.",
                        location,
                    )
                )
        if "source_statement" in claim and not _non_empty_string(claim["source_statement"]):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} field 'source_statement' must be a non-empty string.",
                    location,
                )
            )
        if "derivation_rule" in claim and claim["derivation_rule"] is not None and not _non_empty_string(
            claim["derivation_rule"]
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} field 'derivation_rule' must be a non-empty string or null.",
                    location,
                )
            )
        if "qualification" in claim and not _non_empty_string(claim["qualification"]):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} field 'qualification' must be a non-empty string.",
                    location,
                )
            )
        if "severity_if_wrong" in claim and claim["severity_if_wrong"] not in CLAIM_SEVERITIES:
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Claim {claim_id!s} has invalid severity_if_wrong={claim['severity_if_wrong']!s}.",
                    location,
                )
            )

    @staticmethod
    def _duplicate_ids(ids: list[str]) -> list[Finding]:
        return [
            Finding(
                "V-001",
                "RELEASE_BLOCKING",
                f"Duplicate Claim ID: {claim_id}.",
                claim_id,
            )
            for claim_id, count in sorted(Counter(ids).items())
            if count > 1
        ]

    @staticmethod
    def _dangling_dependencies(
        claims: list[Mapping[str, Any]], id_set: set[str]
    ) -> list[Finding]:
        findings: list[Finding] = []
        for claim in claims:
            claim_id = claim.get("claim_id")
            dependencies = claim.get("depends_on")
            if not _claim_id_list(dependencies):
                continue
            for dependency in dependencies:
                if dependency not in id_set:
                    findings.append(
                        Finding(
                            "V-003",
                            "RELEASE_BLOCKING",
                            f"Claim {claim_id!s} depends on missing Claim {dependency}.",
                            claim_id if isinstance(claim_id, str) else None,
                        )
                    )
        return findings

    @staticmethod
    def _dependency_cycles(
        claims: list[Mapping[str, Any]], id_set: set[str]
    ) -> list[Finding]:
        graph: dict[str, list[str]] = {}
        for claim in claims:
            claim_id = claim.get("claim_id")
            dependencies = claim.get("depends_on")
            if not isinstance(claim_id, str) or claim_id not in id_set:
                continue
            if not _claim_id_list(dependencies):
                graph[claim_id] = []
                continue
            graph[claim_id] = sorted(
                dependency for dependency in dependencies if dependency in id_set
            )

        state: dict[str, int] = {claim_id: 0 for claim_id in graph}
        cycles: set[tuple[str, ...]] = set()

        for start in sorted(graph):
            if state[start] != 0:
                continue
            state[start] = 1
            path = [start]
            positions = {start: 0}
            frames: list[tuple[str, Iterator[str]]] = [(start, iter(graph[start]))]

            while frames:
                node, dependencies = frames[-1]
                try:
                    dependency = next(dependencies)
                except StopIteration:
                    frames.pop()
                    state[node] = 2
                    positions.pop(node, None)
                    path.pop()
                    continue

                dependency_state = state.get(dependency, 0)
                if dependency_state == 0:
                    state[dependency] = 1
                    positions[dependency] = len(path)
                    path.append(dependency)
                    frames.append((dependency, iter(graph.get(dependency, []))))
                elif dependency_state == 1:
                    cycle = path[positions[dependency] :] + [dependency]
                    cycles.add(_canonical_cycle(cycle))

        return [
            Finding(
                "V-004",
                "RELEASE_BLOCKING",
                f"Dependency-cycle witness: {' -> '.join(cycle)}.",
                cycle[0],
            )
            for cycle in sorted(cycles)
        ]

    @staticmethod
    def _status_combinations(claims: list[Mapping[str, Any]]) -> list[Finding]:
        findings: list[Finding] = []
        for claim in claims:
            claim_id = claim.get("claim_id")
            claim_status = claim.get("claim_status")
            evidence_status = claim.get("evidence_status")
            if claim_status not in CLAIM_STATUSES or evidence_status not in EVIDENCE_STATUSES:
                continue

            cell = STATUS_MATRIX.get(claim_status, {}).get(evidence_status)
            if cell is None:
                findings.append(
                    Finding(
                        "V-005",
                        "RELEASE_BLOCKING",
                        (
                            f"Illegal §3.5 combination for {claim_id!s}: "
                            f"claim_status={claim_status}, evidence_status={evidence_status}."
                        ),
                        claim_id if isinstance(claim_id, str) else None,
                    )
                )
            elif cell == "FLAG" and not _non_empty_string(claim.get("qualification")):
                findings.append(
                    Finding(
                        "V-024",
                        "RELEASE_BLOCKING",
                        f"FLAG matrix cell for {claim_id!s} requires an explicit qualification.",
                        claim_id if isinstance(claim_id, str) else None,
                    )
                )
        return findings

    @staticmethod
    def _derived_claims(
        claims: list[Mapping[str, Any]], by_id: Mapping[str, Mapping[str, Any]]
    ) -> list[Finding]:
        findings: list[Finding] = []
        for claim in claims:
            if claim.get("claim_type") != "DERIVED":
                continue
            claim_id = claim.get("claim_id")
            derivation_rule = claim.get("derivation_rule")
            dependencies = claim.get("depends_on")
            missing: list[str] = []
            if not _non_empty_string(derivation_rule):
                missing.append("derivation_rule")
            if not _claim_id_list(dependencies) or not dependencies:
                missing.append("at least one dependency/premise")
            if missing:
                findings.append(
                    Finding(
                        "V-008",
                        "RELEASE_BLOCKING",
                        f"Derived Claim {claim_id!s} requires {' and '.join(missing)}.",
                        claim_id if isinstance(claim_id, str) else None,
                    )
                )
                continue

            claim_status = claim.get("claim_status")
            if claim_status == "SUPPORTED":
                allowed_premise_statuses = {"SUPPORTED"}
            elif claim_status == "SUPPORTED_CONDITIONAL":
                allowed_premise_statuses = {"SUPPORTED", "SUPPORTED_CONDITIONAL"}
            else:
                continue

            inadmissible: list[str] = []
            for dependency in dependencies:
                premise = by_id.get(dependency)
                if premise is None:
                    continue
                premise_status = premise.get("claim_status")
                if premise_status in CLAIM_STATUSES and premise_status not in allowed_premise_statuses:
                    inadmissible.append(f"{dependency}={premise_status}")
            if inadmissible:
                findings.append(
                    Finding(
                        "V-006D",
                        "RELEASE_BLOCKING",
                        (
                            f"Derived Claim {claim_id!s} outranks its premises: "
                            + ", ".join(inadmissible)
                            + "."
                        ),
                        claim_id if isinstance(claim_id, str) else None,
                    )
                )
        return findings


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and all(isinstance(item, str) for item in value)
    )


def _claim_id_list(value: Any) -> bool:
    return (
        _string_list(value)
        and len(value) == len(set(value))
        and all(CLAIM_ID_PATTERN.fullmatch(item) for item in value)
    )


def _decision_conditions(value: Any) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and all(
            isinstance(item, Mapping)
            and set(item) == {"decision_id", "equals"}
            and _non_empty_string(item["decision_id"])
            and _non_empty_string(item["equals"])
            for item in value
        )
    )


def _canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
    body = nodes[:-1]
    start = min(range(len(body)), key=body.__getitem__)
    smallest = tuple(body[start:] + body[:start])
    return smallest + (smallest[0],)


def validate_ledger(ledger: Mapping[str, Any]) -> ValidationResult:
    """Validate one ledger and return all deterministic findings."""

    if not isinstance(ledger, Mapping):
        return ValidationResult(
            (
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    "Ledger root must be an object.",
                ),
            )
        )
    return LedgerValidator().validate(ledger)


def validate_ledger(ledger: Mapping[str, Any]) -> ValidationResult:
    """Convenience entry point for callers that do not need a validator instance."""

    return LedgerValidator().validate(ledger)
