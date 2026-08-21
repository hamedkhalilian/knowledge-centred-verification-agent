"""Deterministic Claim Ledger validators.

The protocol in ``prompts/master_prompt_v2.2.md`` is authoritative. This module
implements only checks that can be evaluated mechanically from the currently
modelled Run, Claim, Source, Evidence, and edge objects; semantic truth and
source adequacy remain separate review concerns.
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
EVIDENCE_RETRIEVAL_METHODS = frozenset(
    {
        "primary_text",
        "official_portal",
        "licensed_database",
        "authoritative_secondary",
        "secondary_summary",
        "internal_source",
        "none",
    }
)
EVIDENCE_STANCES = frozenset({"AFFIRMS", "QUALIFIES", "CONTRADICTS", "SILENT"})
SOURCE_KINDS = frozenset(
    {
        "statute",
        "regulation",
        "judgment",
        "regulator_guidance",
        "professional_standard",
        "official_guidance",
        "commentary",
        "academic",
        "secondary",
        "data",
        "internal",
    }
)
SOURCE_ACCESS_VALUES = frozenset({"PUBLIC", "LICENSED", "PAYWALLED", "INTERNAL"})
SOURCE_REQUIRED_FIELDS = frozenset(
    {
        "source_id",
        "kind",
        "identifier",
        "title",
        "version_label",
        "version_date",
        "access",
        "locator",
        "sufficient_for",
    }
)
SOURCE_FIELDS = frozenset({*SOURCE_REQUIRED_FIELDS, "evidence_level", "provenance_note"})
EVIDENCE_REQUIRED_FIELDS = frozenset(
    {
        "evidence_id",
        "source_id",
        "retrieved_at",
        "retrieval_method",
        "fragment",
        "extract",
        "supersession_checked",
        "superseded_by",
        "queries_attempted",
        "search_scope",
        "agent",
        "prompt_version",
    }
)
EVIDENCE_FIELDS = EVIDENCE_REQUIRED_FIELDS

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
        findings.extend(self._evidence_source_links(ledger))
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
    def _evidence_source_links(ledger: Mapping[str, Any]) -> list[Finding]:
        """Validate Source/Evidence provenance when those ledger views exist."""
        findings: list[Finding] = []
        raw_sources = ledger.get("sources")
        raw_evidence = ledger.get("evidence")
        raw_edges = ledger.get("edges")

        if raw_sources is None and raw_evidence is None and raw_edges is None:
            return findings

        def object_list(raw: Any, field: str) -> list[Mapping[str, Any]]:
            if raw is None:
                return []
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Ledger field '{field}' must be a list.",
                    )
                )
                return []
            objects: list[Mapping[str, Any]] = []
            for index, item in enumerate(raw):
                if not isinstance(item, Mapping):
                    findings.append(
                        Finding(
                            "V-000",
                            "RELEASE_BLOCKING",
                            f"{field.title()} item at index {index} must be an object.",
                        )
                    )
                    continue
                objects.append(item)
            return objects

        sources = object_list(raw_sources, "sources")
        evidence = object_list(raw_evidence, "evidence")
        edges = object_list(raw_edges, "edges")

        source_id_values: list[str] = []
        for index, source in enumerate(sources):
            LedgerValidator._validate_source_structure(source, index, findings)
            source_id = source.get("source_id")
            if not _non_empty_string(source_id):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Source at index {index} has an invalid 'source_id'.",
                    )
                )
                continue
            source_id_values.append(source_id)
        source_ids = set(source_id_values)
        for source_id, count in sorted(Counter(source_id_values).items()):
            if count > 1:
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Duplicate Source ID: {source_id}.",
                    )
                )

        evidence_id_values: list[str] = []
        evidence_methods: dict[str, list[Any]] = {}
        for index, item in enumerate(evidence):
            LedgerValidator._validate_evidence_structure(item, index, findings)
            evidence_id = item.get("evidence_id")
            if not _non_empty_string(evidence_id):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Evidence at index {index} has an invalid 'evidence_id'.",
                    )
                )
                continue
            evidence_id_values.append(evidence_id)
            evidence_methods.setdefault(evidence_id, []).append(
                item.get("retrieval_method")
            )
        evidence_ids = set(evidence_id_values)
        for evidence_id, count in sorted(Counter(evidence_id_values).items()):
            if count > 1:
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Duplicate Evidence ID: {evidence_id}.",
                    )
                )

        raw_claims = ledger.get("claims")
        claim_ids: set[str] = set()
        if isinstance(raw_claims, Sequence) and not isinstance(raw_claims, (str, bytes)):
            claim_ids = {
                claim.get("claim_id")
                for claim in raw_claims
                if isinstance(claim, Mapping)
                and _non_empty_string(claim.get("claim_id"))
            }

        retrieved_from: dict[str, list[str]] = {}
        for edge in edges:
            edge_type = edge.get("type")
            if edge_type == "EVIDENCED_BY":
                claim_id = edge.get("from")
                evidence_id = edge.get("to")
                stance = edge.get("stance")
                if not _non_empty_string(claim_id) or not _non_empty_string(evidence_id):
                    findings.append(
                        Finding(
                            "V-000",
                            "RELEASE_BLOCKING",
                            "EVIDENCED_BY edges require non-empty 'from' and 'to' IDs.",
                        )
                    )
                    continue
                if claim_id not in claim_ids:
                    findings.append(
                        Finding(
                            "V-003",
                            "RELEASE_BLOCKING",
                            f"EVIDENCED_BY edge references missing Claim {claim_id}.",
                            claim_id,
                        )
                    )
                if evidence_id not in evidence_ids:
                    findings.append(
                        Finding(
                            "V-003",
                            "RELEASE_BLOCKING",
                            f"EVIDENCED_BY edge references missing Evidence {evidence_id}.",
                            claim_id,
                        )
                    )
                if not isinstance(stance, str) or stance not in EVIDENCE_STANCES:
                    findings.append(
                        Finding(
                            "V-000",
                            "RELEASE_BLOCKING",
                            f"EVIDENCED_BY edge has invalid stance={stance!s}.",
                            claim_id,
                        )
                    )
                elif (
                    evidence_id in evidence_ids
                    and "none" in evidence_methods.get(evidence_id, [])
                    and stance != "SILENT"
                ):
                    findings.append(
                        Finding(
                            "V-025",
                            "RELEASE_BLOCKING",
                            f"Negative-retrieval Evidence {evidence_id} requires stance=SILENT.",
                            claim_id,
                        )
                    )
                continue
            if edge_type != "RETRIEVED_FROM":
                continue
            evidence_id = edge.get("from")
            source_id = edge.get("to")
            if not _non_empty_string(evidence_id) or not _non_empty_string(source_id):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        "RETRIEVED_FROM edges require non-empty 'from' and 'to' IDs.",
                    )
                )
                continue
            retrieved_from.setdefault(evidence_id, []).append(source_id)
            if evidence_id not in evidence_ids:
                findings.append(
                    Finding(
                        "V-003",
                        "RELEASE_BLOCKING",
                        f"RETRIEVED_FROM edge references missing Evidence {evidence_id}.",
                    )
                )
            if source_id not in source_ids:
                findings.append(
                    Finding(
                        "V-003",
                        "RELEASE_BLOCKING",
                        f"RETRIEVED_FROM edge references missing Source {source_id}.",
                    )
                )

        for item in evidence:
            evidence_id = item.get("evidence_id")
            if not _non_empty_string(evidence_id):
                continue
            if "stance" in item:
                findings.append(
                    Finding(
                        "V-025",
                        "RELEASE_BLOCKING",
                        f"Evidence {evidence_id} stores stance globally instead of on an EVIDENCED_BY edge.",
                    )
                )
            method = item.get("retrieval_method")
            source_id = item.get("source_id")
            linked_sources = retrieved_from.get(evidence_id, [])
            if not isinstance(method, str) or method not in EVIDENCE_RETRIEVAL_METHODS:
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Evidence {evidence_id} has invalid retrieval_method={method!s}.",
                    )
                )
                continue

            if method == "none":
                if source_id is not None or linked_sources:
                    findings.append(
                        Finding(
                            "V-003",
                            "RELEASE_BLOCKING",
                            f"Negative-retrieval Evidence {evidence_id} must have no Source or RETRIEVED_FROM edge.",
                        )
                    )
                continue

            if not _non_empty_string(source_id) or source_id not in source_ids:
                findings.append(
                    Finding(
                        "V-003",
                        "RELEASE_BLOCKING",
                        f"Positive-retrieval Evidence {evidence_id} references missing Source {source_id!s}.",
                    )
                )
            if linked_sources != [source_id]:
                findings.append(
                    Finding(
                        "V-003",
                        "RELEASE_BLOCKING",
                        f"Evidence {evidence_id} must have exactly one RETRIEVED_FROM edge to {source_id!s}.",
                    )
                )

        return findings

    @staticmethod
    def _validate_source_structure(
        source: Mapping[str, Any], index: int, findings: list[Finding]
    ) -> None:
        source_id = source.get("source_id")
        for field in sorted(SOURCE_REQUIRED_FIELDS - source.keys()):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source at index {index} is missing required field '{field}'.",
                )
            )
        for field in sorted(source.keys() - SOURCE_FIELDS):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source {source_id!s} has unknown field '{field}'.",
                )
            )

        kind = source.get("kind")
        if "kind" in source and (
            not isinstance(kind, str) or kind not in SOURCE_KINDS
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source {source_id!s} has invalid kind={kind!s}.",
                )
            )
        access = source.get("access")
        if "access" in source and (
            not isinstance(access, str) or access not in SOURCE_ACCESS_VALUES
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source {source_id!s} has invalid access={access!s}.",
                )
            )
        for field in ("identifier", "title"):
            if field in source and not _non_empty_string(source[field]):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Source {source_id!s} field '{field}' must be a non-empty string.",
                    )
                )
        for field in ("version_label", "locator"):
            if field in source and source[field] is not None and not isinstance(
                source[field], str
            ):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Source {source_id!s} field '{field}' must be a string or null.",
                    )
                )
        if "version_date" in source and source["version_date"] is not None and not _iso_date(
            source["version_date"]
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source {source_id!s} field 'version_date' must be an ISO date or null.",
                )
            )
        if "sufficient_for" in source and not _non_empty_string_list(
            source["sufficient_for"]
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source {source_id!s} field 'sufficient_for' must be a list of strings.",
                )
            )
        if "evidence_level" in source:
            level = source["evidence_level"]
            if level is not None and (
                isinstance(level, bool) or not isinstance(level, int) or level < 1
            ):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Source {source_id!s} field 'evidence_level' must be a positive integer or null.",
                    )
                )
        if "provenance_note" in source and not _non_empty_string(
            source["provenance_note"]
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Source {source_id!s} field 'provenance_note' must be a non-empty string.",
                )
            )

    @staticmethod
    def _validate_evidence_structure(
        evidence: Mapping[str, Any], index: int, findings: list[Finding]
    ) -> None:
        evidence_id = evidence.get("evidence_id")
        for field in sorted(EVIDENCE_REQUIRED_FIELDS - evidence.keys()):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Evidence at index {index} is missing required field '{field}'.",
                )
            )
        for field in sorted(evidence.keys() - EVIDENCE_FIELDS):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Evidence {evidence_id!s} has unknown field '{field}'.",
                )
            )

        if "retrieved_at" in evidence and not _iso_date(evidence["retrieved_at"]):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Evidence {evidence_id!s} field 'retrieved_at' must be an ISO date.",
                )
            )
        for field in ("fragment", "extract", "search_scope"):
            if field in evidence and evidence[field] is not None and not isinstance(
                evidence[field], str
            ):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Evidence {evidence_id!s} field '{field}' must be a string or null.",
                    )
                )
        if "supersession_checked" in evidence and not isinstance(
            evidence["supersession_checked"], bool
        ):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Evidence {evidence_id!s} field 'supersession_checked' must be boolean.",
                )
            )
        for field in ("superseded_by", "queries_attempted"):
            if field in evidence and not _string_list(evidence[field]):
                findings.append(
                    Finding(
                        "V-000",
                        "RELEASE_BLOCKING",
                        f"Evidence {evidence_id!s} field '{field}' must be a list of strings.",
                    )
                )
        if "agent" in evidence and not _non_empty_string(evidence["agent"]):
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Evidence {evidence_id!s} field 'agent' must be a non-empty string.",
                )
            )
        if "prompt_version" in evidence and evidence["prompt_version"] != "v2.2":
            findings.append(
                Finding(
                    "V-000",
                    "RELEASE_BLOCKING",
                    f"Evidence {evidence_id!s} field 'prompt_version' must equal 'v2.2'.",
                )
            )

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
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
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


def _non_empty_string_list(value: Any) -> bool:
    return _string_list(value) and all(_non_empty_string(item) for item in value)


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
