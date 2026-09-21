"""Importer for a Claude.ai data export.

No connector reads Claude.ai chats or Projects, so the only route into the
ledger is the account's own data export: Settings, then Privacy, then Export
data. The export arrives as a set of per-category ZIP archives — among them
``conversations`` and ``projects`` — so this module accepts the archives
themselves, a directory holding them, or an already-unzipped tree.

Categories this module does not understand are skipped and named in the
result rather than guessed at.

What this module does and does not do follows the repository's split. Turning
a conversation into a project record is judgment and stays with the agent.
Unpacking the archive, grouping it, and flagging the turns that *look* like
friction is mechanical, so it runs here.

Friction is the point of reading chats at all. A Drive summary holds the
polished result and a repository holds the finished code; only the transcript
holds the moment the author was wrong and said so. That material is what
keeps a post from reading like a report, so the importer surfaces it rather
than leaving it buried in thousands of turns.
"""

from __future__ import annotations

import json
import re
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Markers of a turn where the author's understanding moved. Deliberately
# generous: this is a shortlist for a human to judge, not a classifier. Both
# languages the corpus is written in are covered.
FRICTION_MARKERS = (
    # English
    r"\bwait\b",
    r"\bactually\b",
    r"\bi was wrong\b",
    r"\bthat'?s wrong\b",
    r"\bnot (?:quite|right|true)\b",
    r"\bdoesn'?t (?:make sense|work|follow)\b",
    r"\bi don'?t (?:understand|get|see)\b",
    r"\bwhy (?:does|is|would|not)\b",
    r"\bbut then\b",
    r"\bhold on\b",
    r"\bcorrection\b",
    r"\bi thought\b",
    r"\bturns out\b",
    r"\bmistake\b",
    # Persian
    r"صبر کن",
    r"اشتباه",
    r"درست نیست",
    r"متوجه نمی",
    r"نمی‌فهمم",
    r"چرا این",
    r"پس چی",
    r"فکر می‌کردم",
    r"معلوم شد",
)

_FRICTION_RE = re.compile("|".join(FRICTION_MARKERS), re.IGNORECASE)

DEFAULT_MAX_CHARS = 40_000


@dataclass
class Conversation:
    """One exported chat, normalised across export-format variations."""

    uuid: str
    name: str
    created_at: str
    project: str = ""
    turns: list[tuple[str, str]] = field(default_factory=list)

    @property
    def human_turns(self) -> list[str]:
        return [text for sender, text in self.turns if sender == "human"]

    def friction_candidates(self) -> list[str]:
        """Human turns that carry a marker of a reversal or a stuck point.

        Only the author's own turns are scanned. What the assistant said is
        not evidence that the author changed their mind.
        """
        found: list[str] = []
        for text in self.human_turns:
            for line in (ln.strip() for ln in text.splitlines()):
                if len(line) >= 15 and _FRICTION_RE.search(line):
                    found.append(line)
        return found


def _message_text(message: dict[str, Any]) -> str:
    """Pull text out of a message across the shapes the export has used."""
    text = message.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts: list[str] = []
    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n".join(parts).strip()


def _sender(message: dict[str, Any]) -> str:
    raw = str(message.get("sender") or message.get("role") or "").lower()
    return "human" if raw in ("human", "user") else "assistant"


def parse_conversations(payload: Any, project_names: dict[str, str] | None = None) -> list[Conversation]:
    """Normalise ``conversations.json`` into :class:`Conversation` records."""
    project_names = project_names or {}
    if isinstance(payload, dict):
        payload = payload.get("conversations", [])
    if not isinstance(payload, list):
        return []

    conversations: list[Conversation] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        raw_messages = entry.get("chat_messages")
        if not isinstance(raw_messages, list):
            raw_messages = entry.get("messages")
        if not isinstance(raw_messages, list):
            raw_messages = []

        turns: list[tuple[str, str]] = []
        for message in raw_messages:
            if not isinstance(message, dict):
                continue
            text = _message_text(message)
            if text:
                turns.append((_sender(message), text))

        project_uuid = ""
        project = entry.get("project")
        if isinstance(project, dict):
            project_uuid = str(project.get("uuid") or "")
        elif isinstance(project, str):
            project_uuid = project
        project_uuid = project_uuid or str(entry.get("project_uuid") or "")

        conversations.append(
            Conversation(
                uuid=str(entry.get("uuid") or entry.get("id") or ""),
                name=str(entry.get("name") or entry.get("title") or "untitled"),
                created_at=str(entry.get("created_at") or ""),
                project=project_names.get(project_uuid, project_uuid),
                turns=turns,
            )
        )
    return conversations


def parse_projects(payload: Any) -> list[dict[str, Any]]:
    """Normalise ``projects.json`` into records carrying their knowledge docs.

    A Project's docs are the material the author curated deliberately, which
    makes them denser than any single conversation. Shapes vary across export
    versions, so anything unrecognised is dropped rather than guessed at.
    """
    if isinstance(payload, dict):
        payload = payload.get("projects", [])
    if not isinstance(payload, list):
        return []
    projects: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        docs: list[dict[str, str]] = []
        raw_docs = entry.get("docs")
        if not isinstance(raw_docs, list):
            raw_docs = entry.get("documents")
        if isinstance(raw_docs, list):
            for doc in raw_docs:
                if not isinstance(doc, dict):
                    continue
                content = doc.get("content") or doc.get("text") or ""
                if not isinstance(content, str) or not content.strip():
                    continue
                docs.append(
                    {
                        "filename": str(
                            doc.get("filename") or doc.get("name") or "untitled"
                        ),
                        "content": content.strip(),
                    }
                )
        projects.append(
            {
                "uuid": str(entry.get("uuid") or ""),
                "name": str(entry.get("name") or entry.get("uuid") or "untitled"),
                "description": str(entry.get("description") or ""),
                "created_at": str(entry.get("created_at") or ""),
                "docs": docs,
            }
        )
    return projects


def render_project_digest(project: dict[str, Any], max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Render a Project and its knowledge docs as one harvestable digest."""
    lines = [
        f"# Project: {project['name']}",
        "",
        f"- project: `{project['uuid']}`",
        f"- created: {project.get('created_at') or 'unknown'}",
        f"- documents: {len(project['docs'])}",
        "",
        "> Raw exported material. Not a project record. Harvest it into",
        "> `corpus/projects/` and cite this file in `source_ref`.",
        "",
    ]
    if project.get("description"):
        lines += ["## Description", "", project["description"], ""]
    budget = max_chars
    for doc in project["docs"]:
        if budget <= 0:
            lines += ["", "_[digest truncated]_"]
            break
        body = doc["content"][:budget]
        budget -= len(body)
        lines += [f"## {doc['filename']}", "", body, ""]
    return "\n".join(lines).rstrip() + "\n"


def parse_project_names(payload: Any) -> dict[str, str]:
    """Map project UUIDs to their names, so chats can be grouped by project."""
    if isinstance(payload, dict):
        payload = payload.get("projects", [])
    if not isinstance(payload, list):
        return {}
    names: dict[str, str] = {}
    for entry in payload:
        if isinstance(entry, dict) and entry.get("uuid"):
            names[str(entry["uuid"])] = str(entry.get("name") or entry["uuid"])
    return names


def slugify(value: str, fallback: str = "untitled") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or fallback


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _is_zip(path: Path) -> bool:
    return path.is_file() and zipfile.is_zipfile(path)


@contextmanager
def unpacked(source: Path) -> Iterator[Path]:
    """Yield a directory tree to search, extracting archives when needed.

    The export ships as several ZIPs. Passing the download folder, a single
    archive, or an unzipped tree all work; anything extracted goes to a
    temporary directory that is removed on exit, so raw transcripts are never
    left inside the repository by accident.
    """
    archives: list[Path] = []
    if _is_zip(source):
        archives = [source]
    elif source.is_dir():
        archives = sorted(p for p in source.iterdir() if _is_zip(p))

    if not archives:
        yield source
        return

    with tempfile.TemporaryDirectory(prefix="postforge-export-") as tmp:
        root = Path(tmp)
        for archive in archives:
            target = root / archive.stem
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as zf:
                for member in zf.infolist():
                    # Refuse absolute paths and parent traversal in member
                    # names; an export is trusted but this costs nothing.
                    name = Path(member.filename)
                    if name.is_absolute() or ".." in name.parts:
                        continue
                    zf.extract(member, target)
        if source.is_dir():
            yield root if not any(source.glob("*.json")) else source
        else:
            yield root


def locate(source: Path) -> tuple[Path | None, Path | None]:
    """Find the conversations file and the projects source in a tree.

    The projects side ships two ways. Older exports carry a single
    ``projects.json`` holding every project; the current one carries a
    ``projects/`` directory with one JSON file per project. Both are returned
    as a single path, and :func:`load_projects_payload` resolves whichever it
    turns out to be.
    """
    if source.is_file():
        if source.name == "projects.json":
            return None, source
        if source.suffix == ".json":
            return source, None
    if not source.is_dir():
        return None, None
    conversations = next(iter(sorted(source.rglob("conversations.json"))), None)
    projects: Path | None = next(iter(sorted(source.rglob("projects.json"))), None)
    if projects is None:
        for directory in sorted(source.rglob("projects")):
            if directory.is_dir() and any(directory.glob("*.json")):
                projects = directory
                break
    return conversations, projects


def load_projects_payload(path: Path | None) -> Any:
    """Read the projects source, whether a single file or a directory.

    A directory yields the same list a single ``projects.json`` would, so
    everything downstream stays unaware of which layout the export used.
    """
    if path is None:
        return []
    if path.is_dir():
        records: list[Any] = []
        for entry in sorted(path.glob("*.json")):
            try:
                records.append(json.loads(entry.read_text("utf-8")))
            except json.JSONDecodeError:
                continue
        return records
    return _read_json(path)


def render_digest(conversation: Conversation, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Render one conversation as a readable digest for the agent to harvest.

    The author's turns are kept whole because they carry the intent and the
    friction. Assistant turns are truncated, since their role here is to make
    the author's turns legible, not to be mined for content.
    """
    lines = [
        f"# {conversation.name}",
        "",
        f"- conversation: `{conversation.uuid}`",
        f"- created: {conversation.created_at or 'unknown'}",
        f"- project: {conversation.project or '(none)'}",
        f"- turns: {len(conversation.turns)}",
        "",
        "> Raw exported material. Not a project record. Harvest it into",
        "> `corpus/projects/` and cite this file in `source_ref`.",
        "",
    ]

    candidates = conversation.friction_candidates()
    if candidates:
        lines += ["## Friction candidates", ""]
        lines += [
            "Lines from the author's own turns that carry a marker of a",
            "reversal or a stuck point. A shortlist to judge, not a verdict.",
            "",
        ]
        lines += [f"- {line}" for line in candidates[:25]]
        lines += [""]

    lines += ["## Transcript", ""]
    budget = max_chars
    for sender, text in conversation.turns:
        if budget <= 0:
            lines += ["", "_[digest truncated]_"]
            break
        body = text if sender == "human" else text[:600]
        if sender == "assistant" and len(text) > 600:
            body += " …"
        block = f"**{sender}:** {body}"
        budget -= len(block)
        lines += [block, ""]
    return "\n".join(lines).rstrip() + "\n"


def import_export(
    source: Path,
    destination: Path,
    *,
    min_turns: int = 4,
    max_chars: int = DEFAULT_MAX_CHARS,
    limit: int | None = None,
) -> list[Path]:
    """Write one digest per substantial conversation into ``destination``.

    ``min_turns`` drops one-off questions, which are numerous and carry no
    project. Nothing here writes a project record: that judgment is the
    agent's, and a record is written only after a human-readable digest has
    actually been read.
    """
    with unpacked(source) as tree:
        conversations_path, projects_path = locate(tree)
        if conversations_path is None and projects_path is None:
            raise FileNotFoundError(
                f"Found neither conversations.json nor projects.json under "
                f"{source}. Point this at the Claude.ai export: the folder of "
                "downloaded .zip archives, one archive, or an unzipped tree."
            )
        conversations_payload = (
            _read_json(conversations_path) if conversations_path else []
        )
        projects_payload = load_projects_payload(projects_path)

    projects = parse_projects(projects_payload)
    project_names = {p["uuid"]: p["name"] for p in projects if p["uuid"]}
    conversations = parse_conversations(conversations_payload, project_names)

    keep = [c for c in conversations if len(c.turns) >= min_turns]
    keep.sort(key=lambda c: c.created_at, reverse=True)
    if limit is not None:
        keep = keep[:limit]

    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    used: set[str] = set()

    for project in projects:
        if not project["docs"] and not project["description"]:
            continue
        if not project["name"]:
            continue
        stem = f"project--{slugify(project['name'])}"
        used.add(stem)
        path = destination / f"{stem}.md"
        path.write_text(render_project_digest(project, max_chars), "utf-8")
        written.append(path)

    for conversation in keep:
        stem = slugify(conversation.name)
        if conversation.project:
            stem = f"{slugify(conversation.project)}--{stem}"
        candidate = stem
        suffix = 2
        while candidate in used:
            candidate = f"{stem}-{suffix}"
            suffix += 1
        used.add(candidate)
        path = destination / f"{candidate}.md"
        path.write_text(render_digest(conversation, max_chars), "utf-8")
        written.append(path)
    return written


__all__ = [
    "Conversation",
    "parse_conversations",
    "parse_projects",
    "load_projects_payload",
    "parse_project_names",
    "render_project_digest",
    "unpacked",
    "render_digest",
    "import_export",
    "locate",
    "slugify",
    "FRICTION_MARKERS",
]
