"""Bridge detection: the part of the pipeline a human cannot do by hand.

Summarising one project is easy and low value. The expensive, interesting
question is which *pair* of unrelated projects shares a structure. That is the
question this module answers deterministically, so that the agent spends its
judgment on the few pairs worth writing about rather than on rediscovering
them each run.

Scoring, in three factors:

``shared_weight``
    Smoothed inverse document frequency, summed over the shared concepts. A
    concept that appears in every project carries almost no weight; a concept
    that appears in exactly two carries a lot. This is the whole trick: a
    bridge is interesting in proportion to how *rarely* the two sides are
    already connected.

``domain_distance``
    ``1.0`` when the two projects share no domain, ``0.5`` on partial overlap,
    ``0.2`` when the domain sets are identical. Two statistics projects
    sharing a statistics concept is not a transfer of ideas.

``evidence_factor``
    ``0.5 + 0.5 * density``, where density saturates at six recorded evidence
    items across the pair. A bridge with hard numbers behind it outranks an
    equally novel one without.
"""

from __future__ import annotations

import math
from collections import Counter

from postforge.ledger import Corpus
from postforge.model import Bridge, Project

EVIDENCE_SATURATION = 6


def concept_document_frequency(projects: list[Project]) -> Counter[str]:
    """How many projects mention each concept."""
    frequency: Counter[str] = Counter()
    for project in projects:
        for concept in set(project.concepts):
            frequency[concept] += 1
    return frequency


def concept_idf(projects: list[Project]) -> dict[str, float]:
    """Smoothed inverse document frequency per concept.

    The ``+ 1`` smoothing keeps a concept shared by every project in a small
    corpus from collapsing to exactly zero, which would make early-stage
    corpora produce no bridges at all.
    """
    total = len(projects)
    frequency = concept_document_frequency(projects)
    return {
        concept: math.log((total + 1) / count)
        for concept, count in frequency.items()
    }


def domain_distance(left: Project, right: Project) -> float:
    left_domains, right_domains = set(left.domains), set(right.domains)
    if not left_domains or not right_domains:
        return 0.5
    if not left_domains & right_domains:
        return 1.0
    if left_domains == right_domains:
        return 0.2
    return 0.5


def evidence_factor(left: Project, right: Project) -> float:
    total = len(left.evidence) + len(right.evidence)
    density = min(1.0, total / EVIDENCE_SATURATION)
    return 0.5 + 0.5 * density


def detect_bridges(
    corpus: Corpus,
    *,
    min_shared: int = 1,
    cross_domain_only: bool = False,
    exclude_published: bool = True,
) -> list[Bridge]:
    """Score every project pair that shares at least ``min_shared`` concepts.

    ``exclude_published`` drops any pair whose shared concepts are already
    fully covered by a published post, so the same bridge is not proposed
    twice across runs.
    """
    projects = corpus.projects
    idf = concept_idf(projects)
    covered: list[frozenset[str]] = [
        frozenset(post.concepts) for post in corpus.published() if post.concepts
    ]

    bridges: list[Bridge] = []
    for index, left in enumerate(projects):
        for right in projects[index + 1 :]:
            shared = sorted(set(left.concepts) & set(right.concepts))
            if len(shared) < min_shared:
                continue
            distance = domain_distance(left, right)
            is_cross = distance >= 1.0
            if cross_domain_only and not is_cross:
                continue
            if exclude_published and any(
                set(shared) <= published for published in covered
            ):
                continue
            weight = sum(idf.get(concept, 0.0) for concept in shared)
            score = weight * distance * evidence_factor(left, right)
            bridges.append(
                Bridge(
                    bridge_id=f"B-{left.project_id}--{right.project_id}",
                    left=left.project_id,
                    right=right.project_id,
                    shared_concepts=shared,
                    score=score,
                    cross_domain=is_cross,
                )
            )
    bridges.sort(key=lambda b: (-b.score, b.bridge_id))
    return bridges


def rank_single_projects(
    corpus: Corpus, archetype: str, *, exclude_published: bool = True
) -> list[tuple[Project, float]]:
    """Rank projects as candidates for a single-project archetype.

    ``showcase`` and ``autopsy`` reward evidence, because those archetypes
    stand on checkable specifics. ``teaching`` rewards distinctive concepts
    instead, because its value is explanatory reach rather than proof.
    """
    idf = concept_idf(corpus.projects)
    covered = {
        frozenset(post.concepts)
        for post in corpus.published()
        if post.concepts
    }
    ranked: list[tuple[Project, float]] = []
    for project in corpus.projects:
        if exclude_published and frozenset(project.concepts) in covered:
            continue
        distinctiveness = sum(idf.get(c, 0.0) for c in set(project.concepts))
        if archetype in ("showcase", "autopsy"):
            if not project.evidence:
                continue
            score = distinctiveness * min(
                1.0, len(project.evidence) / EVIDENCE_SATURATION
            )
        else:
            score = distinctiveness
        ranked.append((project, score))
    ranked.sort(key=lambda pair: (-pair[1], pair[0].project_id))
    return ranked


__all__ = [
    "concept_document_frequency",
    "concept_idf",
    "domain_distance",
    "evidence_factor",
    "detect_bridges",
    "rank_single_projects",
]
