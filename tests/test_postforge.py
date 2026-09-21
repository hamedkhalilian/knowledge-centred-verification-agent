"""Executable tests for the Post-Forge concept ledger.

Every deterministic rule gets a failing fixture and a passing one, matching
the repository's contributing rule for new rule identifiers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from postforge.bridge import (
    concept_idf,
    detect_bridges,
    domain_distance,
    rank_single_projects,
)
from postforge.cli import main
from postforge.ledger import MAX_POST_CHARS, Corpus, blocking, validate
from postforge.model import Post, Project

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_project(project_id: str, **overrides) -> dict:
    record = {
        "project_id": project_id,
        "title": f"Title for {project_id}",
        "source": "manual",
        "source_ref": f"manual:{project_id}",
        "domains": ["alpha"],
        "stage": "active",
        "summary": "A summary long enough to be meaningful.",
        "concepts": ["shared-shape"],
        "evidence": ["one measured outcome"],
        "language": "en",
        "harvested_at": "2026-09-21",
        "notes": "",
    }
    record.update(overrides)
    return record


def build_corpus(tmp_path: Path, projects: list[dict], posts: list[dict] | None = None) -> Corpus:
    (tmp_path / "projects").mkdir(parents=True, exist_ok=True)
    for record in projects:
        (tmp_path / "projects" / f"{record['project_id']}.json").write_text(
            json.dumps(record), "utf-8"
        )
    if posts:
        (tmp_path / "posts").mkdir(parents=True, exist_ok=True)
        for record in posts:
            (tmp_path / "posts" / f"{record['post_id']}.json").write_text(
                json.dumps(record), "utf-8"
            )
    return Corpus.load(tmp_path)


def rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


# --- P-000 --------------------------------------------------------------


def test_p000_flags_empty_ledger(tmp_path: Path) -> None:
    assert "P-000" in rule_ids(validate(build_corpus(tmp_path, [])))


def test_p000_flags_missing_field(tmp_path: Path) -> None:
    corpus = build_corpus(tmp_path, [make_project("a", summary="")])
    assert "P-000" in rule_ids(validate(corpus))


def test_p000_flags_unknown_source_kind(tmp_path: Path) -> None:
    corpus = build_corpus(tmp_path, [make_project("a", source="telepathy")])
    assert "P-000" in rule_ids(validate(corpus))


def test_p000_flags_unknown_stage(tmp_path: Path) -> None:
    corpus = build_corpus(tmp_path, [make_project("a", stage="marinating")])
    assert "P-000" in rule_ids(validate(corpus))


def test_p000_quiet_on_well_formed_project(tmp_path: Path) -> None:
    corpus = build_corpus(tmp_path, [make_project("a")])
    assert "P-000" not in rule_ids(validate(corpus))


# --- P-001 --------------------------------------------------------------


def test_p001_flags_duplicate_project_ids(tmp_path: Path) -> None:
    corpus = Corpus(tmp_path)
    corpus.projects = [
        Project.from_dict(make_project("a")),
        Project.from_dict(make_project("a")),
    ]
    assert "P-001" in rule_ids(validate(corpus))


# --- P-002 --------------------------------------------------------------


def test_p002_flags_post_referencing_unknown_project(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a")],
        [
            {
                "post_id": "P-1",
                "archetype": "teaching",
                "sources": ["ghost"],
                "concepts": ["shared-shape"],
                "status": "candidate",
                "title": "t",
            }
        ],
    )
    assert "P-002" in rule_ids(validate(corpus))


# --- P-003 --------------------------------------------------------------


def test_p003_flags_repeat_of_published_concept_set(tmp_path: Path) -> None:
    posts = [
        {
            "post_id": "P-old",
            "archetype": "teaching",
            "sources": ["a"],
            "concepts": ["x", "y"],
            "status": "published",
            "title": "old",
        },
        {
            "post_id": "P-new",
            "archetype": "teaching",
            "sources": ["a"],
            "concepts": ["y", "x"],
            "status": "candidate",
            "title": "new",
        },
    ]
    corpus = build_corpus(tmp_path, [make_project("a", concepts=["x", "y"])], posts)
    assert "P-003" in rule_ids(validate(corpus))


def test_p003_allows_a_superset_as_a_follow_up(tmp_path: Path) -> None:
    posts = [
        {
            "post_id": "P-old",
            "archetype": "teaching",
            "sources": ["a"],
            "concepts": ["x", "y"],
            "status": "published",
            "title": "old",
        },
        {
            "post_id": "P-new",
            "archetype": "teaching",
            "sources": ["a"],
            "concepts": ["x", "y", "z"],
            "status": "candidate",
            "title": "new",
        },
    ]
    corpus = build_corpus(tmp_path, [make_project("a", concepts=["x", "y", "z"])], posts)
    assert "P-003" not in rule_ids(validate(corpus))


# --- P-004 --------------------------------------------------------------


@pytest.mark.parametrize("archetype", ["showcase", "autopsy"])
def test_p004_flags_evidence_free_showcase(tmp_path: Path, archetype: str) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a", evidence=[])],
        [
            {
                "post_id": "P-1",
                "archetype": archetype,
                "sources": ["a"],
                "concepts": ["shared-shape"],
                "status": "candidate",
                "title": "t",
            }
        ],
    )
    assert "P-004" in rule_ids(validate(corpus))


def test_p004_ignores_teaching_posts_without_evidence(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a", evidence=[])],
        [
            {
                "post_id": "P-1",
                "archetype": "teaching",
                "sources": ["a"],
                "concepts": ["shared-shape"],
                "status": "candidate",
                "title": "t",
            }
        ],
    )
    assert "P-004" not in rule_ids(validate(corpus))


# --- P-006 --------------------------------------------------------------


@pytest.mark.parametrize("bad", ["Hazard Rate", "hazard_rate", "HazardRate", "-hazard"])
def test_p006_flags_non_slug_concepts(tmp_path: Path, bad: str) -> None:
    corpus = build_corpus(tmp_path, [make_project("a", concepts=[bad])])
    assert "P-006" in rule_ids(validate(corpus))


def test_p006_quiet_on_slugs(tmp_path: Path) -> None:
    corpus = build_corpus(tmp_path, [make_project("a", concepts=["hazard-rate", "x1"])])
    assert "P-006" not in rule_ids(validate(corpus))


# --- P-007 --------------------------------------------------------------


def test_p007_flags_missing_body(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a")],
        [
            {
                "post_id": "P-1",
                "archetype": "teaching",
                "sources": ["a"],
                "concepts": ["shared-shape"],
                "status": "candidate",
                "title": "t",
                "body_path": "posts/nowhere.md",
            }
        ],
    )
    assert "P-007" in rule_ids(validate(corpus))


def test_p007_flags_overlong_body(tmp_path: Path) -> None:
    (tmp_path / "posts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "posts" / "long.md").write_text("x" * (MAX_POST_CHARS + 1), "utf-8")
    corpus = build_corpus(
        tmp_path,
        [make_project("a")],
        [
            {
                "post_id": "P-1",
                "archetype": "teaching",
                "sources": ["a"],
                "concepts": ["shared-shape"],
                "status": "candidate",
                "title": "t",
                "body_path": "posts/long.md",
            }
        ],
    )
    assert "P-007" in rule_ids(validate(corpus))


# --- bridge scoring -----------------------------------------------------


def test_domain_distance_ranks_disjoint_above_identical() -> None:
    left = Project.from_dict(make_project("l", domains=["alpha"]))
    right = Project.from_dict(make_project("r", domains=["beta"]))
    same = Project.from_dict(make_project("s", domains=["alpha"]))
    assert domain_distance(left, right) > domain_distance(left, same)


def test_a_universal_concept_carries_less_weight_than_a_rare_one(tmp_path: Path) -> None:
    projects = [
        Project.from_dict(make_project(f"p{i}", concepts=["everywhere"]))
        for i in range(4)
    ]
    projects[0].concepts.append("rare")
    projects[1].concepts.append("rare")
    idf = concept_idf(projects)
    assert idf["rare"] > idf["everywhere"]


def test_cross_domain_bridge_outscores_same_domain_bridge(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [
            make_project("a", domains=["alpha"], concepts=["rare-shape"]),
            make_project("b", domains=["beta"], concepts=["rare-shape"]),
            make_project("c", domains=["alpha"], concepts=["rare-shape"]),
        ],
    )
    bridges = {b.bridge_id: b for b in detect_bridges(corpus)}
    assert bridges["B-a--b"].score > bridges["B-a--c"].score
    assert bridges["B-a--b"].cross_domain is True
    assert bridges["B-a--c"].cross_domain is False


def test_cross_domain_only_filters_same_domain_pairs(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [
            make_project("a", domains=["alpha"]),
            make_project("c", domains=["alpha"]),
        ],
    )
    assert detect_bridges(corpus, cross_domain_only=True) == []


def test_published_bridges_are_excluded_by_default(tmp_path: Path) -> None:
    projects = [
        make_project("a", domains=["alpha"], concepts=["rare-shape"]),
        make_project("b", domains=["beta"], concepts=["rare-shape"]),
    ]
    posts = [
        {
            "post_id": "P-done",
            "archetype": "bridge",
            "sources": ["a", "b"],
            "concepts": ["rare-shape"],
            "status": "published",
            "title": "done",
        }
    ]
    corpus = build_corpus(tmp_path, projects, posts)
    assert detect_bridges(corpus) == []
    assert detect_bridges(corpus, exclude_published=True, cross_domain_only=False) == []
    assert len(detect_bridges(corpus, exclude_published=False)) == 1


def test_showcase_ranking_drops_projects_without_evidence(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [
            make_project("with-evidence", evidence=["a measured outcome"]),
            make_project("no-evidence", evidence=[]),
        ],
    )
    ranked = [p.project_id for p, _ in rank_single_projects(corpus, "showcase")]
    assert ranked == ["with-evidence"]


def test_teaching_ranking_keeps_projects_without_evidence(tmp_path: Path) -> None:
    corpus = build_corpus(tmp_path, [make_project("no-evidence", evidence=[])])
    ranked = [p.project_id for p, _ in rank_single_projects(corpus, "teaching")]
    assert ranked == ["no-evidence"]


# --- the shipped corpus -------------------------------------------------


def test_shipped_corpus_passes_every_rule() -> None:
    corpus = Corpus.load(REPO_ROOT / "corpus")
    findings = validate(corpus)
    assert blocking(findings) == [], [f.to_dict() for f in findings]


def test_shipped_corpus_surfaces_the_cross_domain_bridge_first() -> None:
    """The scorer must rank the statistics/law transfer above same-domain pairs.

    This is the behaviour the whole system exists for: the valuable pair is
    the one whose halves share no field.
    """
    corpus = Corpus.load(REPO_ROOT / "corpus")
    bridges = detect_bridges(corpus)
    assert bridges, "expected at least one bridge in the shipped corpus"
    top = bridges[0]
    assert top.cross_domain is True
    assert {top.left, top.right} == {
        "efron-survival-prediction",
        "bgb-498-consumer-credit",
    }


def test_cli_lint_exits_zero_on_the_shipped_corpus(capsys) -> None:
    assert main(["--corpus", str(REPO_ROOT / "corpus"), "lint"]) == 0


def test_cli_lint_exits_one_on_a_broken_corpus(tmp_path: Path, capsys) -> None:
    (tmp_path / "projects").mkdir(parents=True)
    (tmp_path / "projects" / "bad.json").write_text(
        json.dumps(make_project("bad", concepts=["Not A Slug"])), "utf-8"
    )
    assert main(["--corpus", str(tmp_path), "lint"]) == 1


def test_cli_bridges_emits_json(tmp_path: Path, capsys) -> None:
    assert main(["--corpus", str(REPO_ROOT / "corpus"), "--json", "bridges"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["bridges"][0]["cross_domain"] is True


def test_post_roundtrips_through_dict() -> None:
    post = Post.from_dict(
        {
            "post_id": "P-1",
            "archetype": "bridge",
            "sources": ["a"],
            "concepts": ["x"],
            "status": "draft",
            "title": "t",
        }
    )
    assert Post.from_dict(post.to_dict()) == post
