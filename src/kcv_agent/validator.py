"""Deterministic Claim Ledger validators.

The validator deliberately performs checks that do not benefit from probabilistic
reasoning. Semantic truth and source adequacy remain separate review concerns.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .models import Finding, ValidationResult


ALLOWED_STATUS_COMBINATIONS: dict[str, frozenset[str]] = {
    "VERIFIED": frozenset({"PRIMARY", "AUTHORITATIVE_SECONDARY", "NOT_REQUIRED"}),
    "QUALIFIED": frozenset(
        {"PRIMARY", "AUTHORITATIVE_SECONDARY", "SECONDARY", "SOURCE_CONFLICT"}
    ),
    "UNVERIFIED": frozenset({"SECONDARY", "NOT_RETRIEVED"}),
    "CONTRADICTED": frozenset(
        {"PRIMARY", "AUTHORITATIVE_SECONDARY", "SOURCE_CONFLICT"}
    ),
    "UNRESOLVED": frozenset({"SECONDARY", "NOT_RETRIEVED", "SOURCE_CONFLICT"}),
}


class LedgerValidator:
    """Apply stable graph and state rules to a ledger mapping."""

    def validate(self, ledger: Mapping[str, Any]) -> ValidationResult:
        findings: list[Finding] = []
        claims = self._claims(ledger, findings)
        if claims is None:
            return ValidationResult(tuple(findings))

        ids = [claim.get("id") for claim in claims if isinstance(claim.get("id"), str)]
        id_set = set(ids)

        findings.extend(self._duplicate_ids(ids))
        findings.extend(self._dangling_dependencies(claims, id_set))
        findings.extend(self._dependency_cycles(claims, id_set))
        findings.extend(self._status_combinations(claims))
        findings.extend(self._derived_claims(claims))

        return ValidationResult(tuple(findings))

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
    def _duplicate_ids(ids: list[str]) -> list[Finding]:
        return [
            Finding("V-001", "RELEASE_BLOCKING", f"Duplicate Claim ID: {claim_id}.", claim_id)
            for claim_id, count in sorted(Counter(ids).items())
            if count > 1
        ]

    @staticmethod
    def _dangling_dependencies(
        claims: list[Mapping[str, Any]], id_set: set[str]
    ) -> list[Finding]:
        findings: list[Finding] = []
        for claim in claims:
            claim_id = claim.get("id")
            dependencies = claim.get("dependencies", [])
            if not isinstance(dependencies, Sequence) or isinstance(
                dependencies, (str, bytes)
            ):
                continue
            for dependency in dependencies:
                if isinstance(dependency, str) and dependency not in id_set:
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
            claim_id = claim.get("id")
            dependencies = claim.get("dependencies", [])
            if not isinstance(claim_id, str):
                continue
            if not isinstance(dependencies, Sequence) or isinstance(
                dependencies, (str, bytes)
            ):
                dependencies = []
            graph[claim_id] = sorted(
                dependency
                for dependency in dependencies
                if isinstance(dependency, str) and dependency in id_set
            )

        state: dict[str, int] = {claim_id: 0 for claim_id in graph}
        stack: list[str] = []
        positions: dict[str, int] = {}
        cycles: set[tuple[str, ...]] = set()

        def canonical(nodes: list[str]) -> tuple[str, ...]:
            body = nodes[:-1]
            rotations = [tuple(body[i:] + body[:i]) for i in range(len(body))]
            smallest = min(rotations)
            return smallest + (smallest[0],)

        def visit(node: str) -> None:
            state[node] = 1
            positions[node] = len(stack)
            stack.append(node)
            for dependency in graph.get(node, []):
                if state.get(dependency, 0) == 0:
                    visit(dependency)
                elif state.get(dependency) == 1:
                    cycle = stack[positions[dependency] :] + [dependency]
                    cycles.add(canonical(cycle))
            stack.pop()
            positions.pop(node, None)
            state[node] = 2

        for claim_id in sorted(graph):
            if state[claim_id] == 0:
                visit(claim_id)

        return [
            Finding(
                "V-004",
                "RELEASE_BLOCKING",
                f"Cyclic Claim dependency: {' -> '.join(cycle)}.",
                cycle[0],
            )
            for cycle in sorted(cycles)
        ]

    @staticmethod
    def _status_combinations(claims: list[Mapping[str, Any]]) -> list[Finding]:
        findings: list[Finding] = []
        for claim in claims:
            claim_id = claim.get("id")
            kind = claim.get("kind")
            status = claim.get("status")
            evidence_status = claim.get("evidence_status")
            allowed = ALLOWED_STATUS_COMBINATIONS.get(status)

            illegal = allowed is None or evidence_status not in allowed
            if kind == "DERIVED":
                illegal = illegal or evidence_status != "NOT_REQUIRED"
            elif kind in {"SOURCE", "INTERPRETIVE", "DEFINITION"}:
                illegal = illegal or evidence_status == "NOT_REQUIRED"

            if illegal:
                findings.append(
                    Finding(
                        "V-005",
                        "RELEASE_BLOCKING",
                        (
                            f"Illegal status combination for {claim_id!s}: "
                            f"kind={kind!s}, status={status!s}, "
                            f"evidence_status={evidence_status!s}."
                        ),
                        claim_id if isinstance(claim_id, str) else None,
                    )
                )
        return findings

    @staticmethod
    def _derived_claims(claims: list[Mapping[str, Any]]) -> list[Finding]:
        findings: list[Finding] = []
        for claim in claims:
            if claim.get("kind") != "DERIVED":
                continue
            claim_id = claim.get("id")
            derivation_rule = claim.get("derivation_rule")
            if not isinstance(derivation_rule, str) or not derivation_rule.strip():
                findings.append(
                    Finding(
                        "V-008",
                        "RELEASE_BLOCKING",
                        f"Derived Claim {claim_id!s} has no derivation rule.",
                        claim_id if isinstance(claim_id, str) else None,
                    )
                )
        return findings


def validate_ledger(ledger: Mapping[str, Any]) -> ValidationResult:
    """Convenience entry point for callers that do not need a validator instance."""

    return LedgerValidator().validate(ledger)

