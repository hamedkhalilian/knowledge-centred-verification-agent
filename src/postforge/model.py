"""Data model for the concept ledger.

Every record is plain JSON on disk. The dataclasses here exist to give the
deterministic layer a stable shape to validate against, not to hide the files
behind an ORM. A human should be able to read and edit any corpus file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SOURCE_KINDS = frozenset(
    {"drive", "github", "claude-session", "drop", "manual"}
)
STAGES = frozenset({"idea", "active", "shipped", "archived"})
ARCHETYPES = frozenset({"showcase", "teaching", "autopsy", "bridge"})
POST_STATUSES = frozenset({"candidate", "draft", "approved", "published"})

# How a post opens. Repeating an opening is the fastest way to sound
# machine-made, so the vocabulary is closed and ``P-008`` enforces rotation.
OPENING_MOVES = frozenset(
    {
        "confession",    # a result, then the admission that reverses it
        "misconception", # a plausible wrong belief, stated then broken
        "two-facts",     # two unrelated facts, flat, no connective
        "number-first",  # a figure that does not fit what the reader expects
        "scene",         # a concrete moment, one place, one time
        "refusal",       # the answer was "I do not know", and why that is the result
    }
)

SEVERITY_BLOCKING = "RELEASE_BLOCKING"
SEVERITY_WARNING = "WARNING"

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def is_slug(value: str) -> bool:
    """Concept and identifier slugs are lowercase, hyphen-separated, ASCII."""
    return bool(_SLUG.match(value))


@dataclass(frozen=True)
class Finding:
    """A deterministic rule result. Mirrors the repository's finding style."""

    rule_id: str
    severity: str
    message: str
    target: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "target": self.target,
        }


@dataclass
class Project:
    """One harvested body of work.

    ``evidence`` carries the hard, checkable specifics a post can stand on:
    counts, magnitudes, named protocols, measured outcomes. A project with an
    empty evidence list can still teach, but it cannot carry a showcase post.

    ``friction`` carries the other half, and it is the half that keeps a post
    from reading like a report: moments where the author was stuck, wrong, or
    surprised, and what changed. Evidence is what the work produced; friction
    is what it cost. A post built only from evidence is a status update.
    """

    project_id: str
    title: str
    source: str
    source_ref: str
    domains: list[str]
    stage: str
    summary: str
    concepts: list[str]
    evidence: list[str] = field(default_factory=list)
    friction: list[str] = field(default_factory=list)
    language: str = "en"
    harvested_at: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        return cls(
            project_id=data.get("project_id", ""),
            title=data.get("title", ""),
            source=data.get("source", ""),
            source_ref=data.get("source_ref", ""),
            domains=list(data.get("domains", [])),
            stage=data.get("stage", ""),
            summary=data.get("summary", ""),
            concepts=list(data.get("concepts", [])),
            evidence=list(data.get("evidence", [])),
            friction=list(data.get("friction", [])),
            language=data.get("language", "en"),
            harvested_at=data.get("harvested_at", ""),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "source": self.source,
            "source_ref": self.source_ref,
            "domains": self.domains,
            "stage": self.stage,
            "summary": self.summary,
            "concepts": self.concepts,
            "evidence": self.evidence,
            "friction": self.friction,
            "language": self.language,
            "harvested_at": self.harvested_at,
            "notes": self.notes,
        }


@dataclass
class Bridge:
    """A scored cross-domain overlap between two projects."""

    bridge_id: str
    left: str
    right: str
    shared_concepts: list[str]
    score: float
    cross_domain: bool
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_id": self.bridge_id,
            "left": self.left,
            "right": self.right,
            "shared_concepts": self.shared_concepts,
            "score": round(self.score, 4),
            "cross_domain": self.cross_domain,
            "rationale": self.rationale,
        }


@dataclass
class Post:
    """A rendered view of one or more ledger entries."""

    post_id: str
    archetype: str
    sources: list[str]
    concepts: list[str]
    status: str
    title: str
    opening_move: str = ""
    friction_refs: list[str] = field(default_factory=list)
    language: str = "en"
    body_path: str = ""
    created: str = ""
    published_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Post:
        return cls(
            post_id=data.get("post_id", ""),
            archetype=data.get("archetype", ""),
            sources=list(data.get("sources", [])),
            concepts=list(data.get("concepts", [])),
            status=data.get("status", ""),
            title=data.get("title", ""),
            opening_move=data.get("opening_move", ""),
            friction_refs=list(data.get("friction_refs", [])),
            language=data.get("language", "en"),
            body_path=data.get("body_path", ""),
            created=data.get("created", ""),
            published_at=data.get("published_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "post_id": self.post_id,
            "archetype": self.archetype,
            "sources": self.sources,
            "concepts": self.concepts,
            "status": self.status,
            "title": self.title,
            "opening_move": self.opening_move,
            "friction_refs": self.friction_refs,
            "language": self.language,
            "body_path": self.body_path,
            "created": self.created,
            "published_at": self.published_at,
        }
