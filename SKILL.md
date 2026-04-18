---
name: auto-memex
description: "Auto Memex: Personal LLM-Wiki knowledge base system. Builds and maintains an interconnected markdown knowledge base using LLMs. Use when managing wiki pages, answering questions with citations, or organizing research. Based on Karpathy's LLM Wiki pattern. NOTE: This is a standalone wiki skill, separate from Hermes built-in llm-wiki."
compatibility: Requires Python 3.14+, wiki vault path (WIKI_VAULT env var), optional LLM for queries
metadata:
  author: auto_memex
  version: "1.0"
  hermes:
    category: knowledge-management
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

### Lint Wiki
```bash
python scripts/lint_wiki.py --vault /path/to/vault
python scripts/lint_wiki.py --vault /path/to/vault --fix
```

### Vault Orientation
```bash
python scripts/orient_wiki.py
```

## Integration

This skill integrates with Hermes Agent via external skill directories. Configure in `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - /home/hbtjm/lab/auto_memex
```

## Reference

See [references/llm-wiki-pattern.md](references/llm-wiki-pattern.md) for the original Karpathy LLM Wiki pattern.

## Dependencies

- Python 3.14+
- PyYAML (for frontmatter parsing)
- pytest (for testing)
- ruff (for linting)

Install: `pip install -r requirements.txt`

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