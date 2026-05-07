---
name: auto-memex
description: "Auto Memex: Personal LLM-Wiki knowledge base system. Builds and maintains an interconnected markdown knowledge base using LLMs. Use when managing wiki pages, answering questions with wiki citations, or organizing research. Based on Karpathy's LLM Wiki pattern. NOTE: This is a standalone wiki skill, separate from Hermes built-in llm-wiki."
compatibility: Requires Python 3.14+, wiki vault path (WIKI_VAULT env var), optional LLM for queries
metadata:
  author: auto_memex
  version: "1.1"
  hermes:
    category: knowledge-management
functions:
  lint_wiki:
    description: "Run wiki linter on the vault. Finds orphans, broken links, frontmatter issues, stale content, and tag taxonomy violations. Pass fix=true to auto-correct index completeness, tag taxonomy, and stale content issues."
    args:
      vault: "Path to vault (default: /home/hbtjm/library)"
      fix: "Boolean — run auto-fix for rules 3, 5, 6 (index completeness, stale content, tag taxonomy)"
      verbose: "Boolean — show all issues including informational"
  orient_wiki:
    description: "Summarize vault structure, content statistics, and health summary."
  ingest_source:
    description: "Queue a URL or file for wiki ingestion."
  query_wiki:
    description: "Answer a question using wiki content with citations."
---

# LLM Wiki

This skill implements Karpathy's LLM Wiki pattern — a persistent, compounding knowledge base where an LLM incrementally builds and maintains structured markdown files.

## When to Use

Use this skill when:
- Building a personal knowledge base from sources
- Answering questions with wiki citations
- Ingesting new documents and synthesizing with existing knowledge
-Maintaining wiki health (linting for orphans, broken links, contradictions)
-Organizing research, notes, or project documentation

## Architecture

Three layers:
1. **Raw sources** — immutable source documents (articles, papers, notes)
2. **Wiki** — LLM-generated markdown files (entities, concepts, comparisons, queries)
3. **Schema** — conventions for structure and workflows (SCHEMA.md)

## Core Operations

### Ingest

Process a new source into the wiki:
```
1. read the source document
2. extract key entities, concepts, claims
3. create/update summary page in wiki
4. update index.md with new page link
5. update related entity/concept pages
6. append entry to log.md
```

Tools: `ingest_source.py`, `queue_manager.py`

### Query

Answer questions using wiki content:
```
1. find relevant pages (keyword search)
2. read context from top pages
3. synthesize answer with citations
4. optionally file answer back as new wiki page
```

Tools: `query_wiki.py`

### Lint

Health-check the wiki:
```
1. find orphan pages (no inbound links)
2. detect broken wikilinks
3. check index completeness
4. validate frontmatter (required fields)
5. flag stale content (>90 days)
6. validate tag taxonomy
```

Tools: `lint_wiki.py`

## File Conventions

### Required Files in Vault

```
vault/
├── SCHEMA.md        # conventions, tag taxonomy, thresholds
├── index.md        # catalog of all wiki pages
├── log.md          # chronological activity log
├── content_queue.json  # pending ingests
├── entities/      # entity pages
├── concepts/      # concept pages
├── comparisons/    # comparison pages
├── queries/       # query responses (filed back)
├── raw/           # source documents
└── insights/      # synthesized insights
```

### Page Frontmatter

All wiki pages require YAML frontmatter:
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity|concept|comparison|query|summary|transcript
tags: [tag1, tag2]
sources: [url1, url2]
---
```

### Wikilinks

Use `[[Page Name]]` syntax for internal links.

### Log Format

```
## [YYYY-MM-DD] action | details
```

## Commands

### Setup Production
```bash
# Pull from remote to production directory
./scripts/setup-prod.sh
```

### Initialize Vault
```bash
python scripts/init_wiki.py --vault /path/to/vault
```

### Enqueue Source
```bash
python scripts/ingest_source.py --url <url> --type concept --influencer <name>
```

### Query Wiki
```bash
python scripts/query_wiki.py --question "What is X?"
```

### Lint Wiki (Manual)
```bash
python scripts/lint_wiki.py --vault /home/hbtjm/library
python scripts/lint_wiki.py --vault /home/hbtjm/library --fix   # auto-fix rules 3,5,6
```

### Vault Orientation
```bash
python scripts/orient_wiki.py
```

## Automated Lint

The vault is monitored by two layers:

### Layer 1: File watcher (real-time)
A background daemon using `inotifywait` watches the vault and triggers `--fix` on every change:

```bash
bash scripts/lint_watcher.sh start   # start the watcher daemon
bash scripts/lint_watcher.sh stop    # stop it
bash scripts/lint_watcher.sh status   # check if running
```

The watcher auto-fixes rules 3 (index completeness), 5 (stale content), and 6 (tag taxonomy) on every detected change. Full reports are written to `vault/lint.log`.

### Layer 2: Cron (hourly health report)
A cron job runs a full non-fix lint every hour and delivers the report locally. Use `cronjob` tool to manage it:
```
cronjob list  → find the job ID
cronjob run <id>  → trigger immediately
cronjob remove <id>  → disable
```

## Integration

This skill lives at `~/.paradigm/hermes/auto-memex/` (external skill directory). It is already loaded by Hermes via the skills directory. No additional configuration needed.

Invoke lint directly:
```bash
python3 ~/.paradigm/hermes/auto-memex/scripts/lint_wiki.py --vault /home/hbtjm/library --fix
```

## Reference

See [references/llm-wiki-pattern.md](references/llm-wiki-pattern.md) for the original Karpathy LLM Wiki pattern.

See [references/system-checkup-2026-04-30.md](references/system-checkup-2026-04-30.md) for vault lint state, remaining manual work, and automation layer status.

## Dependencies

- Python 3.14+
- PyYAML (for frontmatter parsing)
- pytest (for testing)
- ruff (for linting)

Install: `pip install -r requirements.txt`

## PITFALLS & LESSONS LEARNED

### Batch Fix Misses Top-Level Files with Hyphen Prefixes
The `batch_fix_wiki.py` script processes files correctly, but some top-level vault files start with hyphens (e.g., `-ai-ethics-&-misinformation.md`). These may show as "0 files modified" in batch output but still appear as CRITICAL in lint output. Workaround: run batch_fix with explicit path or process manually:
```bash
python scripts/batch_fix_wiki.py --rule 4 --dry-run  # verify before fixing
```
Root cause: glob pattern interaction with hyphen-starting filenames. Fixed in v1.1+.

### Fedora Path Escaping in Glob Patterns
When running commands with glob patterns on Fedora 44, avoid `./*` escaping in Python subprocess calls. Use explicit paths:
```python
# WRONG
subprocess.run(["bash", "-c", f"python3 {p} 2>&1"], ...)

# RIGHT  
subprocess.run(["python3", "/home/hbtjm/.paradigm/hermes/auto-memex/scripts/lint_wiki.py"], ...)
```

### Rule 9 Exemption for log/SCHEMA
The 18 "oversized" pages flagged by Rule 9 include:
- `log.md` — append-only chronological log (by design oversized)
- `log-YYYY-MM-DD.md` — dated logs
- `SCHEMA.md` — definition/convention file

These are intentionally large and should be exempted. The linter checks for `f.stem.lower() in {"log", "schema"}` and skips them.

### Watcher Service Startup (Fedora 44)
The systemd user service `vault-lint-watcher.service` may exit immediately on Fedora 44 due to inotifywait timing. Alternative: run manually in background:
```bash
nohup bash /home/hbtjm/.paradigm/hermes/auto-memex/scripts/lint_watcher.sh start > /dev/null 2>&1 &
```
Check status: `bash scripts/lint_watcher.sh status`

## Verification

Run tests:
```bash
pytest tests/ -v
```

Run lint:
```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

Run CI locally:
```bash
act --job lint
act --job test
```

Or with Drone CI:
```bash
drone exec
```