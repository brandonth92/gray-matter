# Gray Matter

A lightweight "company brain" framework for AI-assisted knowledge work.

The substrate is deliberately boring: plain Markdown folders, READMEs, and wiki-links. Obsidian is optional as a viewer — the vault itself is just folders, files, and links. On top of that, Gray Matter adds an append-only **touchpoint pipeline**: it scans dated local source material, finds person-related evidence, and appends one-line dated entries with provenance links to canonical People notes. "What's been up with this person lately?" gets a live, cited answer instead of a static file reread.

## Why append-only?

Bots rewriting curated notes breaks trust in a knowledge base fast. Gray Matter enforces the opposite:

- **Append-only by construction** — the pipeline never edits existing content. It only adds a `## Touchpoints` section with dated, sourced one-liners.
- **Human review gate** — extraction produces candidate JSON for review. Nothing touches a note until it's explicitly approved.
- **Hash-guarded dedupe** — processed sources are recorded by content hash, so re-runs never duplicate entries.
- **Atomic + verified** — snapshot before write, byte-level read-back verification after, batch state persisted on every success.

## Components

| File | Role |
|---|---|
| `extract.py` | scan dated `.md` sources → candidate touchpoints (JSON) |
| `apply.py` | validate + append reviewed touchpoints atomically, with verification |
| `tests/` | pytest suite covering extraction, idempotency, guards, dry-run, and CLI receipts |

Status: **v1 proven on live data** (350+ real session transcripts, batch-state and dead-receipt fixes baked in).

## Roadmap

- **Self-budgeting** — packaged per-project usage reporting for agents
- **Email ingestion** — flagship pattern: billing-statement-ready email → workflow nudge → learned cadence → proactive calendar/digest placement
- **Proactive pattern engine** — recurring rhythms graduate into nudges before you have to ask

## Design notes

- Summaries state what happened — no inference about feelings or outcomes beyond what the source says.
- Every applied entry carries a wiki-link (or path) to its evidence source.
- The pipeline refuses empty or draft-flagged summaries, invalid dates, and path-escape targets.

## License

MIT