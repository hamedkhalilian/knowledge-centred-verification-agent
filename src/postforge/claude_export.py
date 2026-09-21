"""Importer for a Claude.ai data export.

No connector reads Claude.ai chats or Projects, so the only route into the
ledger is the account's own data export: Settings, then Privacy, then Export
data. The archive that arrives by email contains ``conversations.json`` and,
where Projects exist, ``projects.json``.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

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


def locate(source: Path) -> tuple[Path | None, Path | None]:
    """Find the two files of interest, whether given a file or a directory."""
    if source.is_file():
        if source.name == "projects.json":
            return None, source
        return source, None
    conversations = next(iter(sorted(source.rglob("conversations.json"))), None)
    projects = next(iter(sorted(source.rglob("projects.json"))), None)
    return conversations, projects


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
    conversations_path, projects_path = locate(source)
    if conversations_path is None:
        raise FileNotFoundError(
            f"No conversations.json found under {source}. Point this at the "
            "unzipped Claude.ai data export."
        )
    project_names = (
        parse_project_names(_read_json(projects_path)) if projects_path else {}
    )
    conversations = parse_conversations(_read_json(conversations_path), project_names)

    keep = [c for c in conversations if len(c.turns) >= min_turns]
    keep.sort(key=lambda c: c.created_at, reverse=True)
    if limit is not None:
        keep = keep[:limit]

    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    used: set[str] = set()
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
    "parse_project_names",
    "render_digest",
    "import_export",
    "locate",
    "slugify",
    "FRICTION_MARKERS",
]
