"""Loading, saving, and deterministic validation of the concept ledger.

The rules below run as code. They do not ask a model to reason harder; they
return stable findings with fixed identifiers, in the same spirit as the
``V-`` rules of the verification validator.

+---------+------------------------------------------------------------+
| Rule    | Check                                                      |
+=========+============================================================+
| ``P-000``| malformed project record, or an empty ledger              |
| ``P-001``| duplicate project identifiers                             |
| ``P-002``| a post or bridge references an unknown project            |
| ``P-003``| a post repeats the concept set of an already published one|
| ``P-004``| a showcase post whose sources carry no evidence           |
| ``P-005``| a bridge between projects that share every domain         |
| ``P-006``| a concept or identifier that is not a lowercase slug      |
| ``P-007``| a post body outside the voice profile's length band       |
+---------+------------------------------------------------------------+

``P-005`` is a warning: a same-domain overlap is a real connection, it is just
not the cross-domain transfer the bridge archetype is built to surface.
Everything else is release blocking.
"""

from __future__ import annotations

import json
from pathlib import Path

from postforge.model import (
    ARCHETYPES,
    POST_STATUSES,
    SEVERITY_BLOCKING,
    SEVERITY_WARNING,
    SOURCE_KINDS,
    STAGES,
    Finding,
    Post,
    Project,
    is_slug,
)

PROJECTS_DIR = "projects"
POSTS_DIR = "posts"

_REQUIRED_PROJECT_FIELDS = (
    "project_id",
    "title",
    "source",
    "source_ref",
    "domains",
    "stage",
    "summary",
    "concepts",
)


class Corpus:
    """An on-disk concept ledger: a directory of project and post records."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.projects: list[Project] = []
        self.posts: list[Post] = []

    @classmethod
    def load(cls, root: Path | str) -> Corpus:
        corpus = cls(Path(root))
        projects_dir = corpus.root / PROJECTS_DIR
        posts_dir = corpus.root / POSTS_DIR
        if projects_dir.is_dir():
            for path in sorted(projects_dir.glob("*.json")):
                corpus.projects.append(
                    Project.from_dict(json.loads(path.read_text("utf-8")))
                )
        if posts_dir.is_dir():
            for path in sorted(posts_dir.glob("*.json")):
                corpus.posts.append(
                    Post.from_dict(json.loads(path.read_text("utf-8")))
                )
        return corpus

    def project_ids(self) -> set[str]:
        return {p.project_id for p in self.projects}

    def by_id(self, project_id: str) -> Project | None:
        for project in self.projects:
            if project.project_id == project_id:
                return project
        return None

    def published(self) -> list[Post]:
        return [p for p in self.posts if p.status == "published"]

    def write_project(self, project: Project) -> Path:
        directory = self.root / PROJECTS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{project.project_id}.json"
        path.write_text(
            json.dumps(project.to_dict(), indent=2, ensure_ascii=False) + "\n",
            "utf-8",
        )
        return path

    def write_post(self, post: Post) -> Path:
        directory = self.root / POSTS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{post.post_id}.json"
        path.write_text(
            json.dumps(post.to_dict(), indent=2, ensure_ascii=False) + "\n",
            "utf-8",
        )
        return path


def validate(corpus: Corpus) -> list[Finding]:
    """Run every deterministic rule and return the findings in rule order."""
    findings: list[Finding] = []
    findings.extend(_p000_structure(corpus))
    findings.extend(_p001_duplicate_ids(corpus))
    findings.extend(_p002_dangling_refs(corpus))
    findings.extend(_p003_repeat_concepts(corpus))
    findings.extend(_p004_showcase_without_evidence(corpus))
    findings.extend(_p006_slugs(corpus))
    findings.extend(_p007_length(corpus))
    return findings


def _p000_structure(corpus: Corpus) -> list[Finding]:
    findings: list[Finding] = []
    if not corpus.projects:
        findings.append(
            Finding(
                "P-000",
                SEVERITY_BLOCKING,
                "The concept ledger contains no project records.",
                str(corpus.root),
            )
        )
        return findings
    for project in corpus.projects:
        target = project.project_id or "<missing project_id>"
        for name in _REQUIRED_PROJECT_FIELDS:
            if not getattr(project, name):
                findings.append(
                    Finding(
                        "P-000",
                        SEVERITY_BLOCKING,
                        f"Project is missing required field {name!r}.",
                        target,
                    )
                )
        if project.source and project.source not in SOURCE_KINDS:
            findings.append(
                Finding(
                    "P-000",
                    SEVERITY_BLOCKING,
                    f"Unknown source kind {project.source!r}; expected one of "
                    f"{sorted(SOURCE_KINDS)}.",
                    target,
                )
            )
        if project.stage and project.stage not in STAGES:
            findings.append(
                Finding(
                    "P-000",
                    SEVERITY_BLOCKING,
                    f"Unknown stage {project.stage!r}; expected one of "
                    f"{sorted(STAGES)}.",
                    target,
                )
            )
    for post in corpus.posts:
        target = post.post_id or "<missing post_id>"
        if post.archetype not in ARCHETYPES:
            findings.append(
                Finding(
                    "P-000",
                    SEVERITY_BLOCKING,
                    f"Unknown archetype {post.archetype!r}; expected one of "
                    f"{sorted(ARCHETYPES)}.",
                    target,
                )
            )
        if post.status not in POST_STATUSES:
            findings.append(
                Finding(
                    "P-000",
                    SEVERITY_BLOCKING,
                    f"Unknown post status {post.status!r}; expected one of "
                    f"{sorted(POST_STATUSES)}.",
                    target,
                )
            )
    return findings


def _p001_duplicate_ids(corpus: Corpus) -> list[Finding]:
    findings: list[Finding] = []
    for collection, label in ((corpus.projects, "project"), (corpus.posts, "post")):
        seen: set[str] = set()
        for record in collection:
            identifier = getattr(
                record, "project_id", None
            ) or getattr(record, "post_id", "")
            if identifier in seen:
                findings.append(
                    Finding(
                        "P-001",
                        SEVERITY_BLOCKING,
                        f"Duplicate {label} identifier {identifier!r}.",
                        identifier,
                    )
                )
            seen.add(identifier)
    return findings


def _p002_dangling_refs(corpus: Corpus) -> list[Finding]:
    known = corpus.project_ids()
    findings: list[Finding] = []
    for post in corpus.posts:
        for source in post.sources:
            if source not in known:
                findings.append(
                    Finding(
                        "P-002",
                        SEVERITY_BLOCKING,
                        f"Post references unknown project {source!r}.",
                        post.post_id,
                    )
                )
    return findings


def _p003_repeat_concepts(corpus: Corpus) -> list[Finding]:
    """A new post must not restate an already published concept set.

    Exact set equality is the test. A post that shares most of its concepts
    but adds at least one is a legitimate follow-up, not a repeat.
    """
    findings: list[Finding] = []
    published = {
        frozenset(post.concepts): post.post_id
        for post in corpus.posts
        if post.status == "published" and post.concepts
    }
    for post in corpus.posts:
        if post.status == "published" or not post.concepts:
            continue
        match = published.get(frozenset(post.concepts))
        if match:
            findings.append(
                Finding(
                    "P-003",
                    SEVERITY_BLOCKING,
                    f"Concept set is identical to published post {match!r}; "
                    "add a new concept or pick a different angle.",
                    post.post_id,
                )
            )
    return findings


def _p004_showcase_without_evidence(corpus: Corpus) -> list[Finding]:
    findings: list[Finding] = []
    for post in corpus.posts:
        if post.archetype not in ("showcase", "autopsy"):
            continue
        evidence_count = 0
        for source in post.sources:
            project = corpus.by_id(source)
            if project:
                evidence_count += len(project.evidence)
        if evidence_count == 0:
            findings.append(
                Finding(
                    "P-004",
                    SEVERITY_BLOCKING,
                    f"A {post.archetype} post needs checkable specifics, but "
                    "none of its source projects records any evidence.",
                    post.post_id,
                )
            )
    return findings


def _p006_slugs(corpus: Corpus) -> list[Finding]:
    findings: list[Finding] = []
    for project in corpus.projects:
        for concept in project.concepts:
            if not is_slug(concept):
                findings.append(
                    Finding(
                        "P-006",
                        SEVERITY_BLOCKING,
                        f"Concept {concept!r} is not a lowercase hyphen slug.",
                        project.project_id,
                    )
                )
        for domain in project.domains:
            if not is_slug(domain):
                findings.append(
                    Finding(
                        "P-006",
                        SEVERITY_BLOCKING,
                        f"Domain {domain!r} is not a lowercase hyphen slug.",
                        project.project_id,
                    )
                )
    return findings


MIN_POST_CHARS = 2000
MAX_POST_CHARS = 2950


def _resolve_body(corpus: Corpus, body_path: str) -> Path | None:
    """Body paths may be written relative to the repository or to the corpus."""
    for base in (Path.cwd(), corpus.root.parent, corpus.root):
        candidate = base / body_path
        if candidate.is_file():
            return candidate
    return None


def _p007_length(corpus: Corpus) -> list[Finding]:
    """A post body must sit inside the length band the voice profile sets.

    The band is calibrated on the reference post, which runs 2,812 characters.
    Below the floor a post has skipped its evidence run; above the ceiling it
    collides with LinkedIn's 3,000-character limit.
    """
    findings: list[Finding] = []
    for post in corpus.posts:
        if not post.body_path:
            continue
        path = _resolve_body(corpus, post.body_path)
        if path is None:
            findings.append(
                Finding(
                    "P-007",
                    SEVERITY_BLOCKING,
                    f"Post body {post.body_path!r} does not exist.",
                    post.post_id,
                )
            )
            continue
        length = len(path.read_text("utf-8").strip())
        if not MIN_POST_CHARS <= length <= MAX_POST_CHARS:
            findings.append(
                Finding(
                    "P-007",
                    SEVERITY_BLOCKING,
                    f"Post body is {length} characters; the voice profile band "
                    f"is {MIN_POST_CHARS}-{MAX_POST_CHARS}.",
                    post.post_id,
                )
            )
    return findings


def blocking(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == SEVERITY_BLOCKING]


__all__ = [
    "Corpus",
    "validate",
    "blocking",
    "SEVERITY_WARNING",
    "MIN_POST_CHARS",
    "MAX_POST_CHARS",
]
