# LLM Wiki Pattern

Based on Andrej Karpathy's concept: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

## Core Idea

Instead of just retrieving from raw documents at query time, the LLM **incrementally builds and maintains a persistent wiki** — a structured, interlinked collection of markdown files that sits between you and the raw sources.

When you add a new source, the LLM doesn't just index it for later retrieval. It reads it, extracts the key information, and integrates it into the existing wiki — updating entity pages, revising topic summaries, noting where new data contradicts old claims.

The key difference: **the wiki is a persistent, compounding artifact.**

## Three Layers

### 1. Raw Sources
- Your curated collection of source documents
- Articles, papers, images, data files
- Immutable — LLM reads but never modifies

### 2. The Wiki
- LLM-generated markdown files
- Summaries, entity pages, concept pages, comparisons
- LLM owns this layer entirely
- Creates pages, updates them when sources arrive
- Maintains cross-references

### 3. Schema (SCHEMA.md)
- Tells the LLM how the wiki is structured
- Conventions for wikilinks, frontmatter, page types
- Workflows for ingesting, querying, linting

## Operations

### Ingest
1. Drop new source into raw collection
2. LLM reads source, extracts key info
3. Creates summary page in wiki
4. Updates index.md
5. Updates related entity/concept pages
6. Appends entry to log.md

### Query
1. LLM reads index.md first for relevant pages
2. Reads context from top pages
3. Synthesizes answer with citations
4. Optionally files answer back as new wiki page

### Lint
1. Find orphans (no inbound links)
2. Detect broken wikilinks
3. Check index completeness
4. Validate frontmatter
5. Flag stale content
6. Validate tag taxonomy

## Index vs Log

**index.md** — content-oriented
- Catalog of all wiki pages
- Link + one-line summary per page
- Organized by category (entities, concepts, etc.)
- LLM updates on every ingest

**log.md** — chronological
- Append-only record
- Format: `## [YYYY-MM-DD] action | details`
- Unix tools parseable: `grep "^## \[" log.md | tail -5`

## Tools

### CLI Tools (included)
- `init_wiki.py` — Initialize new vault
- `ingest_source.py` — Enqueue sources for processing
- `query_wiki.py` — Query wiki with natural language
- `lint_wiki.py` — Health-check wiki
- `orient_wiki.py` — Vault orientation summary

### Optional
- [qmd](https://github.com/tobi/qmd) — Local search engine with BM25/vector search + LLM re-ranking

## Tips

- **Obsidian Web Clipper** for quick source ingestion
- **Download images locally** to raw/assets/
- **Obsidian graph view** to see wiki shape
- **Marp** for slide decks from wiki content
- **Dataview** for frontmatter queries
- **Git** for version history and collaboration

## Why This Works

The tedious part of maintaining a knowledge base is the bookkeeping: updating cross-references, keeping summaries current, noting contradictions. Humans abandon wikis because maintenance burden grows faster than value. LLMs don't get bored, don't forget updates, and can touch 15 files in one pass.

The human's job: curate sources, direct analysis, ask good questions.
The LLM's job: everything else.

## Note

This document describes the idea, not a specific implementation. Directory structure, schema conventions, and tooling depend on your domain and preferences. Everything is modular — pick what's useful, ignore what isn't.