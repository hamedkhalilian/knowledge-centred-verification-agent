"""Post-Forge: a concept-ledger-first generator for LinkedIn drafts.

The package mirrors the repository's governing idea. The concept ledger is the
semantic source of truth about a body of work; a LinkedIn post is a rendered
view of one or more ledger entries. Judgment work (reading a project, naming
its concepts, writing prose) belongs to the agent. The rules in this package
run as code and return stable, machine-readable findings.
"""

from postforge.model import Bridge, Finding, Post, Project

__all__ = ["Bridge", "Finding", "Post", "Project"]
__version__ = "0.1.0"
