"""Small, dependency-free result models for deterministic validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Finding:
    """One stable validator finding."""

    rule_id: str
    severity: str
    message: str
    claim_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Complete deterministic result for one ledger."""

    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not any(
            finding.severity in {"ERROR", "RELEASE_BLOCKING"}
            for finding in self.findings
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "finding_count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
        }

