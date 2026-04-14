# LLM-Wiki Implementation Roadmap

**Date:** 2026-04-13
**Status:** Draft — in progress
**Vault:** `/home/hbtjm/library`

---

## Background

The vault at `/home/hbtjm/library` currently has **380 lint issues** from a prior queue-based worker system (lib_bak). That system failed because:

1. **No frontmatter enforcement** — worker wrote files without YAML frontmatter, no created/updated dates, no type/tags
2. **Filename instability** — spaces, `&`, `;` in filenames broke wikilink resolution
3. **No index.md maintenance** — catalog never populated
4. **No log.md discipline** — only one create entry, no ongoing actions logged
5. **Generic prompts** — `hermes chat` called with freeform prompts, no schema enforcement, no conventions
6. **No linting in the loop** — no health checks after writes

---

## Revised Architecture

### Pattern: Queue + Worker (Simple, Async)

```
ingest_source.py  →  content_queue.json  →  worker.sh (loop)  →  hermes chat → wiki pages
                                         →  mark done

query_wiki.py     →  read index + pages  →  hermes chat synthesis  →  stdout
```

**Why this pattern:**
- Leverages existing authenticated `hermes chat` (no API keys, no credit tracking)
- Async processing — sources enqueued and processed in background
- Simple CLI interface — `ingest_source.py --url <url>` and `query_wiki.py --question <q>`
- Worker is a daemon — processes queue continuously

### What Must Change vs. lib_bak

| Problem | Old Approach | New Approach |
|---------|-------------|--------------|
| No frontmatter | Worker freeform prompt | Prompt enforces: YAML frontmatter required, created/updated, type, tags from SCHEMA |
| Filename instability | Worker wrote whatever | Prompt enforces: `filename: kebab-case-no-spaces.md`, normalize spaces → underscores |
| No index update | Never touched index.md | Prompt enforces: add new page to index.md section after write |
| No log update | Never touched log.md | Prompt enforces: append `## [YYYY-MM-DD] ingest | Title` after write |
| No lint gate | Blind writes | After worker completes, optionally run `lint_wiki.py --fix` |

### Phase 6 Scope (Minimal)

**Goal:** Get a working ingest + query loop that produces clean wiki pages.

`ingest_source.py`:
- CLI: `python ingest_source.py --url <url> [--influencer <name>] [--type concept|entity]`
- Adds JSON task to `content_queue.json` (id, url, influencer, type, title, status=Unassigned)
- Does NOT invoke LLM — just enqueues. LLM processing happens in worker.

`query_wiki.py`:
- CLI: `python query_wiki.py --question <question>`
- Reads index.md + relevant concept/entity pages based on question keywords
- Invokes `hermes chat` with the collected context + question
- Returns synthesized answer to stdout

**NOT in Phase 6** (defer to testing/optimization):
- Direct LLM API calls (Anthropic, etc.)
- Credential tracking
- Advanced deduplication / entity registry
- MCP integration

---

## Roadmap

### Phase 6: Implement Ingest + Query (Simple Pattern)
- [ ] `ingest_source.py` — enqueue CLI (no LLM, just queue management)
- [ ] `query_wiki.py` — query CLI (reads wiki, invokes hermes chat for synthesis)
- [ ] Improved `worker.sh` — update prompt template to enforce frontmatter, filename normalization, index/log updates
- [ ] Test: enqueue a URL, verify worker creates a clean page with frontmatter

### Phase 7: Testing
- [ ] Run `lint_wiki.py` against vault — verify frontmatter coverage improved
- [ ] Test `query_wiki.py` with 3-5 questions — verify answers cite wiki pages
- [ ] Test that index.md and log.md are being updated correctly
- [ ] Manual inspection of 5 created pages — frontmatter, wikilinks, content quality

### Phase 8: Red Teaming / Evaluation
- [ ] Broken wikilinks test — create page with `[[NonExistent]]`, verify lint catches it
- [ ] Frontmatter completeness test — create page without tags, verify lint catches it
- [ ] Index completeness test — create file on disk but don't add to index, verify lint catches it
- [ ] Orphan detection test — create page with no inbound links, verify lint catches it
- [ ] Filename normalization test — ingest source that would create `Data Breaches.md`, verify it becomes `data-breaches.md`
- [ ] Staleness test — set updated date >90 days ago, verify downgrade behavior
- [ ] Query quality test — ask a question where answer requires cross-referencing 2+ pages
- [ ] Concurrency test — enqueue 3 sources simultaneously, verify worker processes without conflicts
- [ ] Log rotation test — verify log.md format is consistent and append-only

### Phase 9: Architecture, Optimizations, Reliability
- [ ] Analyze red team findings — identify root causes of failures
- [ ] Design entity registry — prevent duplicate pages for same concept (e.g., both `AI` and `Artificial-Intelligence`)
- [ ] Improve prompt templates — based on failure patterns from red team
- [ ] Add `--dry-run` mode to ingest — preview what would be created before enqueueing
- [ ] Improve filename normalization — handle `&`, `;`, special chars consistently
- [ ] Add frontmatter migration — script to retroactively add frontmatter to existing pages
- [ ] Consider direct LLM API vs hermes chat tradeoffs — cost, speed, reliability

### Phase 10: New Skill
- [ ] Synthesize all learnings into `llm-wiki-v2` skill for Hermes
- [ ] Document invocation patterns (how to call ingest/query/lint/orient)
- [ ] Include vault-specific conventions (Hal's preferences, path, domain)
- [ ] Include red team findings as pitfalls in the skill
- [ ] Save to `~/.hermes/skills/llm-wiki-v2/`

---

## Key Decisions to Make During Roadmap

1. **Filename convention:** `kebab-case` (recommended) vs `snake_case` vs `PascalCase`
   - Recommendation: kebab-case — most readable, standard for URLs, avoids space issues
   - Normalize: spaces → `-`, `&` → `and`, `;` → removed, multiple dashes → single

2. **Frontmatter fields required:**
   - `title`, `created`, `updated`, `type`, `tags`, `sources`
   - `confidence` field (high/stale) for staleness tracking

3. **Wiki location:** Already `/home/hbtjm/library` — confirmed

4. **Ingest batch size:** One source at a time (per Karpathy + MehmetGoekce) — don't batch

5. **Worker concurrency:** Single worker (fcntl locking on queue file) — safe, simple

6. **Query synthesis:** Use `hermes chat` with context from relevant pages — confirmed approach

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Worker creates pages without frontmatter again | Enforce in prompt template, verify with lint after test |
| Wikilinks break due to filename normalization | Test normalization in isolation before end-to-end |
| `hermes chat` subprocess times out on long content | Truncate content to 8000 chars, use --timeout flag |
| Queue file grows unbounded | Implement queue rotation or archive completed tasks |
| Multiple workers (future) corrupt queue | fcntl locking + single-worker design for now |

---

## Open Questions

1. Should `query_wiki.py` file its answers back to the wiki as `queries/` pages?
   - Per Karpathy: yes for substantial answers — but needs user confirmation since it writes
2. Should `ingest_source.py` support raw text input (not just URL)?
   - Yes — add `--text` flag for pasted content
3. Should we add `--dry-run` to ingest to preview before enqueueing?
   - Yes — useful for QA before committing to queue
4. How do we handle contradictory information in existing pages?
   - Flag in frontmatter, report in lint, don't auto-overwrite
5. Do we need a stop/retry mechanism for failed queue tasks?
   - Not in Phase 6 — just mark done and log failures