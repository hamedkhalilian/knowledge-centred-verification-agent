# Drop folder

Raw material that no connector can reach: exports from Claude.ai Projects,
pasted transcripts, notes, anything.

Rules:

- One topic per file. Any text format.
- Nothing here is a project record. The agent reads these, writes a record into
  `corpus/projects/`, and leaves the raw file in place as provenance.
- A file is safe to delete once a project record cites it in `source_ref`.
