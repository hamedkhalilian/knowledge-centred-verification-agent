"""Command-line interface for the Post-Forge concept ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from postforge.bridge import concept_document_frequency, detect_bridges, rank_single_projects
from postforge.claude_export import DEFAULT_MAX_CHARS, import_export
from postforge.ledger import Corpus, blocking, validate
from postforge.model import ARCHETYPES

DEFAULT_CORPUS = Path("corpus")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="postforge",
        description="Inspect and check the Post-Forge concept ledger.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help="Path to the corpus directory (default: ./corpus)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("lint", help="Run the deterministic ledger rules")
    sub.add_parser("status", help="Summarise the corpus")

    bridges = sub.add_parser("bridges", help="Rank cross-project concept bridges")
    bridges.add_argument("--top", type=int, default=10)
    bridges.add_argument("--min-shared", type=int, default=1)
    bridges.add_argument(
        "--cross-domain-only",
        action="store_true",
        help="Drop pairs that share a domain",
    )
    bridges.add_argument(
        "--include-published",
        action="store_true",
        help="Do not filter pairs already covered by a published post",
    )

    candidates = sub.add_parser(
        "candidates", help="Rank single projects for an archetype"
    )
    candidates.add_argument(
        "--archetype", choices=sorted(ARCHETYPES - {"bridge"}), default="showcase"
    )
    candidates.add_argument("--top", type=int, default=10)

    imp = sub.add_parser(
        "import-claude",
        help="Unpack a Claude.ai data export into corpus/drop/ as digests",
    )
    imp.add_argument(
        "source",
        type=Path,
        help="The unzipped export directory, or conversations.json itself",
    )
    imp.add_argument(
        "--min-turns",
        type=int,
        default=4,
        help="Skip conversations shorter than this (default: 4)",
    )
    imp.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="Transcript budget per digest",
    )
    imp.add_argument(
        "--limit", type=int, default=None, help="Keep only the N most recent"
    )

    return parser


def _emit(payload: dict, lines: list[str], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        for line in lines:
            print(line)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        corpus = Corpus.load(args.corpus)
    except (OSError, json.JSONDecodeError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}")
        return 2

    if args.command == "lint":
        findings = validate(corpus)
        errors = blocking(findings)
        payload = {
            "ok": not errors,
            "findings": [f.to_dict() for f in findings],
        }
        lines = (
            ["PASS: no deterministic findings"]
            if not findings
            else [
                f"{f.severity} {f.rule_id} [{f.target}]: {f.message}"
                for f in findings
            ]
        )
        _emit(payload, lines, args.as_json)
        return 1 if errors else 0

    if args.command == "status":
        frequency = concept_document_frequency(corpus.projects)
        by_status: dict[str, int] = {}
        for post in corpus.posts:
            by_status[post.status] = by_status.get(post.status, 0) + 1
        payload = {
            "projects": len(corpus.projects),
            "concepts": len(frequency),
            "posts": len(corpus.posts),
            "posts_by_status": by_status,
            "top_concepts": frequency.most_common(10),
        }
        lines = [
            f"projects: {len(corpus.projects)}",
            f"distinct concepts: {len(frequency)}",
            f"posts: {len(corpus.posts)} {by_status or ''}".rstrip(),
            "most connected concepts:",
        ]
        lines += [f"  {count:>2}x {concept}" for concept, count in frequency.most_common(10)]
        _emit(payload, lines, args.as_json)
        return 0

    if args.command == "bridges":
        found = detect_bridges(
            corpus,
            min_shared=args.min_shared,
            cross_domain_only=args.cross_domain_only,
            exclude_published=not args.include_published,
        )[: args.top]
        payload = {"bridges": [b.to_dict() for b in found]}
        lines = []
        for bridge in found:
            marker = "cross-domain" if bridge.cross_domain else "same-domain"
            lines.append(f"{bridge.score:6.3f}  {marker:<12} {bridge.left} <-> {bridge.right}")
            lines.append(f"          shared: {', '.join(bridge.shared_concepts)}")
        if not lines:
            lines = ["no bridges found"]
        _emit(payload, lines, args.as_json)
        return 0

    if args.command == "import-claude":
        destination = args.corpus / "drop"
        try:
            written = import_export(
                args.source,
                destination,
                min_turns=args.min_turns,
                max_chars=args.max_chars,
                limit=args.limit,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if args.as_json:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            else:
                print(f"ERROR: {exc}")
            return 2
        payload = {
            "ok": True,
            "written": len(written),
            "destination": str(destination),
            "files": [str(path) for path in written],
        }
        lines = [
            f"wrote {len(written)} digests to {destination}",
            "",
            "These are raw exported chats, not project records, and they are",
            "git-ignored on purpose. Harvest them, then cite each digest in a",
            "project record's source_ref.",
        ]
        _emit(payload, lines, args.as_json)
        return 0

    if args.command == "candidates":
        ranked = rank_single_projects(corpus, args.archetype)[: args.top]
        payload = {
            "archetype": args.archetype,
            "candidates": [
                {"project_id": p.project_id, "title": p.title, "score": round(s, 4)}
                for p, s in ranked
            ],
        }
        lines = [f"{score:6.3f}  {p.project_id}  {p.title}" for p, score in ranked]
        if not lines:
            lines = ["no candidates found"]
        _emit(payload, lines, args.as_json)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
