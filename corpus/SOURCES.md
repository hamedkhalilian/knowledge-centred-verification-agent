# Harvest queue

Sources that exist but have **not** been read into the concept ledger yet. A
project record is written only after the underlying material has actually been
read. Listing a source here is the honest alternative to inventing a summary
and evidence for it.

Capability note, in the repository's own idiom: there is no connector for
Claude.ai chat Projects. Anything that lives only there reaches the ledger
through the drop folder, not through automated harvest.

## Google Drive — read, not yet harvested

| Source | File ID | Why it is queued |
|---|---|---|
| `claude_kholase-gowers-llm-math` | `1qnSDxWkv4_YCS6LfaSxUOFbVJCC8T0EioFGWZpQErNk` | Gowers on LLMs and mathematics; likely shares `correlation-vs-mechanism` with the Efron record |
| `claude_kholase-maghz-01-amoozeshi` | `18wvCT4RGluT7_t3UHz3_JcTW6UHbPi57u1-eDRWq5kY` | Subject not yet established |
| `kholase-254-amoozeshi-1` | `19T6TfF8ARu4Z3YZWtSbKXBRqqYhn3Wi8BS926jCjPzs` | Teaching-side companion to `hgb-254-bausparkasse` |
| `kholase-254-v23-amoozeshi-1` | `18E3a4YMfj47EjXluRQMs8xj316g17ggQt6upTD6LgnQ` | Revised version of the above |

## Claude Code sessions — metadata only

Session titles and post-turn summaries are readable; transcripts are not. These
need either a drop-folder export or a fresh pass in the session itself.

| Session | What the metadata shows |
|---|---|
| RingMate reader client audit | An audit of a reader client |
| reader-api page 12 garbage blocks classification | Document-parsing quality work, block classification |
| Reader-api and homelab server state snapshot | Infrastructure state capture |
| Design: Mobile memory analysis app | Sift Storage Analyzer, reported as fully implemented |

## Not reachable by any connector

- Claude.ai chat Projects and their knowledge files.
- Anything local to a machine this session cannot see.

Route these through `corpus/drop/` (see `docs/POSTFORGE.md`).
