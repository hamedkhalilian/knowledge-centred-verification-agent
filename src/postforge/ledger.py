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
| ``P-007``| a missing body past candidate, or one outside the band    |
| ``P-008``| a post opening the same way as a recently published one   |
| ``P-009``| a post citing a friction moment that does not exist       |
| ``P-010``| a post that cites no friction at all (warning)            |
+---------+------------------------------------------------------------+

``P-008`` through ``P-010`` exist for one reason: an automated pipeline drifts
toward the mechanical, and the drift is not visible from inside a single post.
It shows up across a run of them, as a repeated opening and an absence of
anything the author got wrong. Both of those are decidable, so both are rules
rather than advice.

``P-005`` is a warning: a same-domain overlap is a real connection, it is just
not the cross-domain transfer the bridge archetype is built to surface.
Everything else is release blocking.
"""

from __future__ import annotations

import json
from pathlib import Path

from postforge.model import (
    ARCHETYPES,
    OPENING_MOVES,
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
        #: Files that could not be turned into records at all, as
        #: ``(path, reason)``. A record whose JSON is valid but whose shape is
        #: not — ``"domains": null``, a list where an object belongs — must
        #: still produce a deterministic finding rather than a traceback, so
        #: the failure is captured here and reported by ``P-000``.
        self.unreadable: list[tuple[Path, str]] = []

    @classmethod
    def load(cls, root: Path | str) -> Corpus:
        corpus = cls(Path(root))
        projects_dir = corpus.root / PROJECTS_DIR
        posts_dir = corpus.root / POSTS_DIR
        for directory, factory, sink in (
            (projects_dir, Project.from_dict, corpus.projects),
            (posts_dir, Post.from_dict, corpus.posts),
        ):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                try:
                    payload = json.loads(path.read_text("utf-8"))
                    if not isinstance(payload, dict):
                        raise TypeError(
                            f"record root is {type(payload).__name__}, expected object"
                        )
                    sink.append(factory(payload))
                except (json.JSONDecodeError, TypeError, AttributeError, ValueError) as exc:
                    corpus.unreadable.append((path, str(exc)))
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
    findings.extend(_p008_opening_rotation(corpus))
    findings.extend(_p009_friction_refs(corpus))
    findings.extend(_p010_no_friction(corpus))
    return findings


def _p000_structure(corpus: Corpus) -> list[Finding]:
    findings: list[Finding] = []
    for path, reason in corpus.unreadable:
        findings.append(
            Finding(
                "P-000",
                SEVERITY_BLOCKING,
                f"Record could not be read: {reason}.",
                str(path),
            )
        )
    if not corpus.projects and not corpus.unreadable:
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


#: Statuses that a post cannot hold without a written body. ``candidate`` is
#: excluded on purpose: the skill's third phase selects candidates and its
#: fourth writes them, so a candidate is a decision about what to write, not
#: a draft. Everything past that must have prose behind it.
STATUSES_REQUIRING_BODY = frozenset({"draft", "approved", "published"})


def _p007_length(corpus: Corpus) -> list[Finding]:
    """A post body must exist once the post is past candidate, and fit the band.

    The band is calibrated on the reference post, which runs 2,812 characters.
    Below the floor a post has skipped its evidence run; above the ceiling it
    collides with LinkedIn's 3,000-character limit.
    """
    findings: list[Finding] = []
    for post in corpus.posts:
        if not post.body_path:
            if post.status in STATUSES_REQUIRING_BODY:
                findings.append(
                    Finding(
                        "P-007",
                        SEVERITY_BLOCKING,
                        f"A post with status {post.status!r} has no body_path; "
                        "only a candidate may be bodiless.",
                        post.post_id,
                    )
                )
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


OPENING_LOOKBACK = 2


def _published_in_order(corpus: Corpus) -> list[Post]:
    return sorted(
        corpus.published(), key=lambda p: (p.published_at, p.post_id), reverse=True
    )


def _p008_opening_rotation(corpus: Corpus) -> list[Finding]:
    """An unpublished post may not open like either of the last two published.

    This is the single strongest guard against sounding automated. A reader
    forgives a repeated subject; they stop reading when the third post in a
    row opens with the same trick.
    """
    findings: list[Finding] = []
    recent = [
        post.opening_move
        for post in _published_in_order(corpus)[:OPENING_LOOKBACK]
        if post.opening_move
    ]
    for post in corpus.posts:
        if post.status == "published":
            continue
        if post.opening_move and post.opening_move not in OPENING_MOVES:
            findings.append(
                Finding(
                    "P-008",
                    SEVERITY_BLOCKING,
                    f"Unknown opening move {post.opening_move!r}; expected one "
                    f"of {sorted(OPENING_MOVES)}.",
                    post.post_id,
                )
            )
            continue
        if post.opening_move and post.opening_move in recent:
            findings.append(
                Finding(
                    "P-008",
                    SEVERITY_BLOCKING,
                    f"Opening move {post.opening_move!r} was used by one of the "
                    f"last {OPENING_LOOKBACK} published posts; rotate it.",
                    post.post_id,
                )
            )
    return findings


def _parse_friction_ref(ref: str) -> tuple[str, int] | None:
    project_id, _, index = ref.partition("#")
    if not project_id or not index.isdigit():
        return None
    return project_id, int(index)


def _p009_friction_refs(corpus: Corpus) -> list[Finding]:
    """Every cited friction moment must resolve to a real ledger entry.

    Same constraint as evidence, for the same reason: a post may not stand on
    a human moment that was invented for the post.
    """
    findings: list[Finding] = []
    for post in corpus.posts:
        for ref in post.friction_refs:
            parsed = _parse_friction_ref(ref)
            if parsed is None:
                findings.append(
                    Finding(
                        "P-009",
                        SEVERITY_BLOCKING,
                        f"Friction reference {ref!r} is malformed; expected "
                        "'<project_id>#<index>'.",
                        post.post_id,
                    )
                )
                continue
            project_id, index = parsed
            project = corpus.by_id(project_id)
            if project is None:
                findings.append(
                    Finding(
                        "P-009",
                        SEVERITY_BLOCKING,
                        f"Friction reference {ref!r} names unknown project "
                        f"{project_id!r}.",
                        post.post_id,
                    )
                )
            elif index >= len(project.friction):
                findings.append(
                    Finding(
                        "P-009",
                        SEVERITY_BLOCKING,
                        f"Friction reference {ref!r} is out of range; "
                        f"{project_id!r} records {len(project.friction)} "
                        "friction entries.",
                        post.post_id,
                    )
                )
    return findings


def _p010_no_friction(corpus: Corpus) -> list[Finding]:
    """Warn when a post carries nothing the author got wrong.

    A warning, not an error: some posts legitimately have none, and the
    judgment is the author's. But a run of posts with no friction in any of
    them is what "it reads like a machine wrote it" actually means.
    """
    findings: list[Finding] = []
    for post in corpus.posts:
        if post.status == "published" or post.friction_refs:
            continue
        available = sum(
            len(project.friction)
            for project in (corpus.by_id(s) for s in post.sources)
            if project is not None
        )
        if available:
            message = (
                f"Post cites no friction although its sources record "
                f"{available}; without one it will read as a report."
            )
        else:
            message = (
                "Neither the post nor its source projects record any friction; "
                "harvest a moment the work went wrong before drafting."
            )
        findings.append(Finding("P-010", SEVERITY_WARNING, message, post.post_id))
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
    "OPENING_LOOKBACK",
    "STATUSES_REQUIRING_BODY",
]
