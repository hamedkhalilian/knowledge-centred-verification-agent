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


# --- Claude.ai export importer ------------------------------------------

from postforge.claude_export import (  # noqa: E402
    Conversation,
    import_export,
    parse_conversations,
    parse_project_names,
    render_digest,
    slugify,
)
from postforge.ledger import OPENING_LOOKBACK  # noqa: E402

EXPORT = [
    {
        "uuid": "c1",
        "name": "Survival analysis for §498",
        "created_at": "2026-09-10T10:00:00Z",
        "project": {"uuid": "proj-1"},
        "chat_messages": [
            {"sender": "human", "text": "Can I model termination as a hazard process?"},
            {
                "sender": "assistant",
                "content": [{"type": "text", "text": "Yes, it is time-to-first-event."}],
            },
            {
                "sender": "human",
                "text": "Wait, that's wrong. The statute inserts a cure period.",
            },
            {"sender": "assistant", "text": "Then the quantity is different."},
            {"sender": "human", "text": "I thought censoring was a nuisance."},
        ],
    },
    {
        "uuid": "c2",
        "name": "quick question",
        "created_at": "2026-09-01T10:00:00Z",
        "chat_messages": [
            {"sender": "human", "text": "hi"},
            {"sender": "assistant", "text": "hello"},
        ],
    },
]


def test_parse_conversations_reads_text_and_content_blocks() -> None:
    conversations = parse_conversations(EXPORT)
    assert [c.uuid for c in conversations] == ["c1", "c2"]
    senders = [sender for sender, _ in conversations[0].turns]
    assert senders == ["human", "assistant", "human", "assistant", "human"]
    assert "time-to-first-event" in conversations[0].turns[1][1]


def test_parse_conversations_accepts_the_messages_role_shape() -> None:
    payload = [
        {
            "uuid": "c9",
            "name": "alt",
            "messages": [
                {"role": "user", "text": "a question"},
                {"role": "assistant", "text": "an answer"},
            ],
        }
    ]
    conversation = parse_conversations(payload)[0]
    assert [sender for sender, _ in conversation.turns] == ["human", "assistant"]


def test_parse_conversations_tolerates_junk() -> None:
    assert parse_conversations(None) == []
    assert parse_conversations(["not a dict"]) == []
    assert parse_conversations({"conversations": EXPORT})[0].uuid == "c1"


def test_project_names_group_conversations() -> None:
    names = parse_project_names([{"uuid": "proj-1", "name": "Hazard models"}])
    conversation = parse_conversations(EXPORT, names)[0]
    assert conversation.project == "Hazard models"


def test_friction_candidates_take_only_the_authors_turns() -> None:
    conversation = parse_conversations(EXPORT)[0]
    candidates = conversation.friction_candidates()
    assert any("that's wrong" in line for line in candidates)
    assert any("I thought censoring" in line for line in candidates)
    assert not any("quantity is different" in line for line in candidates)


def test_friction_candidates_match_persian_markers() -> None:
    conversation = Conversation(
        uuid="x",
        name="fa",
        created_at="",
        turns=[("human", "صبر کن، این درست نیست و باید دوباره نگاه کنم")],
    )
    assert conversation.friction_candidates()


def test_short_lines_are_not_friction() -> None:
    conversation = Conversation(
        uuid="x", name="y", created_at="", turns=[("human", "wait")]
    )
    assert conversation.friction_candidates() == []


def test_render_digest_truncates_on_budget() -> None:
    conversation = parse_conversations(EXPORT)[0]
    assert "[digest truncated]" in render_digest(conversation, max_chars=10)


def test_import_export_skips_short_conversations(tmp_path: Path) -> None:
    source = tmp_path / "export"
    source.mkdir()
    (source / "conversations.json").write_text(json.dumps(EXPORT), "utf-8")
    (source / "projects.json").write_text(
        json.dumps([{"uuid": "proj-1", "name": "Hazard models"}]), "utf-8"
    )
    written = import_export(source, tmp_path / "drop", min_turns=4)
    assert len(written) == 1
    assert written[0].name.startswith("hazard-models--")
    assert "Friction candidates" in written[0].read_text("utf-8")


def test_import_export_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        import_export(tmp_path, tmp_path / "drop")


def test_slugify_falls_back_on_unsluggable_titles() -> None:
    assert slugify("§§§") == "untitled"
    assert slugify("Survival analysis for §498").startswith("survival-analysis")


# --- P-008 opening rotation ---------------------------------------------


def _post(post_id: str, **overrides) -> dict:
    record = {
        "post_id": post_id,
        "archetype": "teaching",
        "sources": ["a"],
        "concepts": ["shared-shape"],
        "status": "candidate",
        "title": post_id,
    }
    record.update(overrides)
    return record


def test_p008_blocks_an_opening_used_by_a_recent_post(tmp_path: Path) -> None:
    posts = [
        _post(
            "P-old",
            status="published",
            opening_move="confession",
            published_at="2026-09-01",
        ),
        _post("P-new", opening_move="confession"),
    ]
    corpus = build_corpus(tmp_path, [make_project("a")], posts)
    assert "P-008" in rule_ids(validate(corpus))


def test_p008_allows_a_rotated_opening(tmp_path: Path) -> None:
    posts = [
        _post(
            "P-old",
            status="published",
            opening_move="confession",
            published_at="2026-09-01",
        ),
        _post("P-new", opening_move="two-facts"),
    ]
    corpus = build_corpus(tmp_path, [make_project("a")], posts)
    assert "P-008" not in rule_ids(validate(corpus))


def test_p008_only_looks_back_a_bounded_number_of_posts(tmp_path: Path) -> None:
    """An opening becomes reusable once it has fallen out of the window."""
    moves = ["confession", "two-facts", "number-first"]
    posts = [
        _post(
            f"P-{i}",
            status="published",
            opening_move=move,
            published_at=f"2026-09-0{i + 1}",
        )
        for i, move in enumerate(moves)
    ]
    posts.append(_post("P-new", opening_move="confession"))
    corpus = build_corpus(tmp_path, [make_project("a")], posts)
    assert len(moves) > OPENING_LOOKBACK
    assert "P-008" not in rule_ids(validate(corpus))


def test_p008_rejects_an_unknown_opening_move(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path, [make_project("a")], [_post("P-1", opening_move="vibes")]
    )
    assert "P-008" in rule_ids(validate(corpus))


# --- P-009 friction references ------------------------------------------


def test_p009_flags_a_malformed_reference(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path, [make_project("a")], [_post("P-1", friction_refs=["a"])]
    )
    assert "P-009" in rule_ids(validate(corpus))


def test_p009_flags_an_unknown_project(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path, [make_project("a")], [_post("P-1", friction_refs=["ghost#0"])]
    )
    assert "P-009" in rule_ids(validate(corpus))


def test_p009_flags_an_out_of_range_index(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a", friction=["one moment"])],
        [_post("P-1", friction_refs=["a#5"])],
    )
    assert "P-009" in rule_ids(validate(corpus))


def test_p009_accepts_a_resolving_reference(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a", friction=["one moment"])],
        [_post("P-1", friction_refs=["a#0"])],
    )
    assert "P-009" not in rule_ids(validate(corpus))


# --- P-010 friction warning ---------------------------------------------


def test_p010_warns_but_does_not_block(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path, [make_project("a", friction=["a moment"])], [_post("P-1")]
    )
    findings = validate(corpus)
    assert "P-010" in rule_ids(findings)
    assert [f for f in blocking(findings) if f.rule_id == "P-010"] == []


def test_p010_is_quiet_once_friction_is_cited(tmp_path: Path) -> None:
    corpus = build_corpus(
        tmp_path,
        [make_project("a", friction=["a moment"])],
        [_post("P-1", friction_refs=["a#0"])],
    )
    assert "P-010" not in rule_ids(validate(corpus))


def test_project_friction_survives_a_roundtrip() -> None:
    project = Project.from_dict(make_project("a", friction=["got this wrong"]))
    assert Project.from_dict(project.to_dict()).friction == ["got this wrong"]


def test_shipped_corpus_records_friction_for_every_project() -> None:
    """Friction is what keeps drafts from reading like status updates."""
    corpus = Corpus.load(REPO_ROOT / "corpus")
    without = [p.project_id for p in corpus.projects if not p.friction]
    assert without == [], f"projects with no recorded friction: {without}"
