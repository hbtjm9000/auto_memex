# LLM-Wiki V2 — Development Plan

**Date:** 2026-04-13  
**Status:** Draft — rewriting from scratch  
**Vault:** `/home/hbtjm/library`  
**Based on:** Phase 7 TDD findings + Hub security review

---

## What We Learned (TDD Findings from Phase 7)

The first implementation was **built to pass a spec, not tested for correctness**. Phase 7 testing revealed four systemic bugs:

| Bug | Root Cause | Severity |
|-----|-----------|----------|
| Double `.md.md` extension | Worker prompt told agent "create at `path.md`" and agent also appended `.md` | CRITICAL — corrupts index |
| Wikilinks to non-existent pages | Worker created `[[Video streaming]]` without verifying page exists | CRITICAL — breaks link graph |
| Tags outside taxonomy | Worker used hardcoded `[video,youtube,influencer,testing]` instead of reading SCHEMA taxonomy | WARNING — tag sprawl |
| Index mismatch | Worker wrote `[[concepts/watch.md]]` to index but filesystem had `watch.md.md` | CRITICAL — integrity failure |

**Core lesson:** The worker prompt was underspecified. The agent filled gaps with plausible-but-wrong behavior.

---

## New Philosophy: Test-First, Convention-First

Instead of writing code then testing, we now:
1. **Write behavioral specs** (these tests) BEFORE implementing
2. **Implement to make tests pass** — no premature optimization
3. **Red team AFTER green** — once tests pass, attack the system

---

## Phase 1: Behavioral Test Suite

**All tests must pass before any user-facing tool is considered "working."**

### Test 1.1 — Frontmatter Completeness
```
Setup:  Create a minimal wiki page with no frontmatter
Action: lint_wiki.py reports CRITICAL
Verify: Issue message mentions which required fields are missing
Fix:    Add frontmatter → lint_wiki.py reports clean for that file
```

### Test 1.2 — Filename Normalization
```
Setup:  Queue a task with title "Data Breaches"
Action: Worker processes task
Verify: File created as `concepts/data-breaches.md` (NOT "data-breaches.md.md")
        No spaces in filename
        No double extensions
```

### Test 1.3 — Wikilink Resolution
```
Setup:  Worker creates page with [[NonExistentPage]]
Action: lint_wiki.py runs
Verify: CRITICAL or WARNING issued for broken wikilink
        (NOT a silent failure — lint MUST catch this)
Fix:    Create NonExistentPage or remove link → lint clean
```

### Test 1.4 — Index-Filesystem Consistency
```
Setup:  Create a file on disk but don't add to index.md
Action: lint_wiki.py --fix runs
Verify: File is added to index.md (auto-fix rule 3)
        OR file is reported as CRITICAL if not in wiki dir
```

### Test 1.5 — Tag Taxonomy Compliance
```
Setup:  Worker creates page with tag "random-tag-not-in-schema"
Action: lint_wiki.py runs
Verify: WARNING issued for unlisted tag
Fix:    Change tag to one in SCHEMA taxonomy → lint clean
```

### Test 1.6 — log.md Format Compliance
```
Setup:  None (log.md exists)
Action: Worker ingests a source
Verify: log.md has entry matching pattern: ## [YYYY-MM-DD] ingest | <title>
        Entry is appended (not inserted mid-file)
```

### Test 1.7 — Query Returns Relevant Answers
```
Setup:  Wiki has pages about "zero trust security"
Action: query_wiki.py --question "what is zero trust?"
Verify: Answer cites specific wiki page(s)
        Answer is NOT "I don't know" when relevant content exists
```

### Test 1.8 — Ingest Enqueue/Dequeue Integrity
```
Setup:  content_queue.json has 3 tasks
Action: Worker processes one task
Verify: Task marked "Done" in queue
        Other 2 tasks remain "Unassigned"
        No task is lost or duplicated
```

### Test 1.9 — Worker Idempotency
```
Setup:  Run worker on same task twice (task reset to Unassigned)
Action: Worker processes task twice
Verify: No duplicate pages created
        index.md has only one entry
        log.md has two entries (expected — each ingest logged)
```

### Test 1.10 — Concurrent Worker Safety
```
Setup:  Start 2 worker processes simultaneously (if supported)
Action: Both process different tasks
Verify: No queue corruption
        fcntl.flock prevents data races
        Both tasks completed correctly
```

---

## Phase 2: Fix All Bugs (Green Phase)

Based on Phase 1 findings, fix the implementation. Expected changes:

### 2.1 — Fix Filename Construction (Critical)
**Problem:** Double `.md.md` from worker.sh line 167: `page_name="$subdir/$page_name.md"`

**Fix options:**
- Option A: Worker prompt specifies `page_name` WITHOUT `.md` (agent adds it)
- Option B: Worker prompt specifies full path without comment about extension
- Option C: Enforce filename check in post-write hook

**Recommendation:** Option A — pass basename without extension, document clearly.

### 2.2 — Add Wikilink Validation Pass
**Problem:** Worker creates `[[Page]]` without checking existence.

**Fix:** Before invoking hermes chat, pre-scan existing pages to build an "allowed targets" list. Include this list in the prompt as a constraint: "Only create wikilinks to these EXISTING pages: [list]"

### 2.3 — Read SCHEMA Taxonomy Before Ingest
**Problem:** Tags hardcoded instead of sourced from SCHEMA.

**Fix:** Worker must read SCHEMA.md tag taxonomy section BEFORE building the prompt. Pass the valid tag list explicitly in the prompt.

### 2.4 — Verify Index After Write
**Problem:** Index entry can mismatch filesystem.

**Fix:** After hermes chat completes, run a verification step: check that the created file exists at the path recorded in index.md. If mismatch, fix index.md entry.

---

## Phase 3: Red Team / Security Review

After Phase 1 tests all pass and Phase 2 bugs fixed.

### 3.1 — Credential Leakage
- Search all scripts for hardcoded API keys, tokens, passwords
- Verify all secrets sourced from env vars only
- Check prompts don't echo sensitive task fields (influencer names are fine)

### 3.2 — Path Traversal
- Try to enqueue a URL with `../` path components
- Try to name a page with `../../etc/passwd`
- Verify all file operations are scoped to vault directory

### 3.3 — Shell Injection
- Try to set page title to `` `rm -rf /` ``
- Try URL: `` https://example.com/`whoami` ``
- Verify subprocess calls use proper quoting or avoid shell=True

### 3.4 — Input Validation
- Enqueue empty URL
- Enqueue URL with very long title (>200 chars)
- Query with empty question
- Verify graceful error handling (no traceback leaks)

### 3.5 — Resource Exhaustion
- Enqueue 1000 tasks at once
- Query that iterates over all 107 pages
- Verify queue file doesn't grow unbounded
- Verify memory usage is bounded

### 3.6 — Concurrent Safety
- Start 2 workers simultaneously, process 10 tasks total
- Verify fcntl.flock prevents queue corruption
- Verify no lost tasks

---

## Phase 4: Architecture & Optimizations

Based on red team findings.

### 4.1 — Entity Registry (Deduplication)
**Problem:** `[[AI]]` and `[[Artificial Intelligence]]` point to same entity.

**Solution:** Maintain a `entities/registry.json`:
```json
{
  "canonical_names": {
    "ai": "artificial-intelligence",
    "artificial-intelligence": "artificial-intelligence"
  },
  "pages": {
    "artificial-intelligence": {
      "path": "entities/artificial-intelligence.md",
      "created": "2026-04-01",
      "aliases": ["ai", "machine-intelligence"]
    }
  }
}
```
Before creating a new entity page, check registry for existing canonical name.

### 4.2 — Prompts as Templates
**Problem:** Prompts embedded in worker.sh are brittle, hard to test.

**Solution:** Store prompts in `~/Riki/Utils/prompts/` as separate `.md` files:
```
prompts/
├── ingest_concept.md    # Prompt template for concept ingestion
├── ingest_entity.md     # Prompt template for entity ingestion
├── query.md             # Prompt template for wiki query
└── lint_report.md       # Prompt template for lint summary
```
Load at runtime, interpolate variables. Makes prompts testable and version-controllable.

### 4.3 — Frontmatter Migration Script
**Problem:** 84 pages lack frontmatter from old worker.

**Solution:** `migrate_frontmatter.py` — batch script to add frontmatter to existing pages:
- Reads SCHEMA.md for type hints
- Uses page filename + content to infer type
- Adds `created` from file mtime, `updated` from today
- Infers tags from content (optional, flag for review)
- Idempotent: only adds missing fields, doesn't overwrite existing

### 4.4 — Dry-Run Mode
**Problem:** Can't preview what ingest would create before committing to queue.

**Solution:** `ingest_source.py --dry-run --url <url>`:
- Fetches content (or transcript for YouTube)
- Runs analysis LLM call to determine: page name, type, tags, existing pages to link to
- Prints preview: "Would create concepts/zero-trust.md with tags [security, zero-trust]"
- Does NOT write to queue
- User confirms → `--dry-run` removed → actually enqueues

### 4.5 — Stop / Retry for Failed Tasks
**Problem:** If hermes chat fails mid-task, task is marked Done anyway.

**Solution:** Add `status: Failed` and `error: <message>` fields to queue. Worker skips Failed tasks unless explicitly retried. Add `queue_manager.py retry <id>` command.

---

## Phase 5: New Skill — `llm-wiki-v2`

Final deliverable: a Hermes skill any user can install and use.

### Skill Design Goals

**For Hermes Users:**
- `skill_call(name='llm-wiki-v2', function='ingest', args={url, influencer, type})` — one-liner
- `skill_call(name='llm-wiki-v2', function='query', args={question})` — one-liner
- `skill_call(name='llm-wiki-v2', function='lint', args={fix: false})` — one-liner
- `skill_call(name='llm-wiki-v2', function='orient', args={})` — vault summary

**For Skill Developers:**
- Self-contained: all logic in skill, no external dependencies beyond hermes tools
- Testable: behavioral tests drive implementation (Phase 1 tests as spec)
- Configurable: wiki path from env var `LLM_WIKI_PATH`
- Idempotent: all operations safe to retry

**For Hub Security Review:**
- No hardcoded credentials
- File operations scoped to configured wiki path
- All API calls opt-in via env vars
- Input validation on all user-facing parameters
- Audit trail via log.md (append-only)

### Skill Structure
```
~/.hermes/skills/llm-wiki-v2/
├── SKILL.md                    # Main skill definition
├── scripts/
│   ├── ingest_source.py       # Enqueue CLI
│   ├── query_wiki.py          # Query CLI
│   ├── worker.sh              # Background worker
│   ├── lint_wiki.py           # Lint engine
│   ├── orient_wiki.py         # Vault summary
│   └── migrate_frontmatter.py  # Batch migration
├── prompts/
│   ├── ingest_concept.md
│   ├── ingest_entity.md
│   └── query.md
├── tests/
│   ├── test_frontmatter.py
│   ├── test_filename_norm.py
│   ├── test_wikilinks.py
│   ├── test_index_consistency.py
│   ├── test_tag_taxonomy.py
│   ├── test_query_relevance.py
│   └── test_queue_integrity.py
├── bin/
│   └── llm-wiki               # CLI wrapper (optional)
└── config/
    └── defaults.yaml          # Default config values
```

### Skill Invocation Patterns

```python
# Ingest a source
skill_call(name='llm-wiki-v2', function='ingest', args={
    'url': 'https://example.com/article',
    'influencer': 'Troy Hunt',
    'type': 'concept'
})

# Query the wiki
skill_call(name='llm-wiki-v2', function='query', args={
    'question': 'what is zero trust architecture?'
})

# Lint the vault
skill_call(name='llm-wiki-v2', function='lint', args={
    'fix': False
})

# Get vault orientation
skill_call(name='llm-wiki-v2', function='orient', args={})
```

### Hub Security Checklist
- [ ] No credentials in code (all from env vars)
- [ ] File paths resolved relative to wiki root, no traversal
- [ ] Subprocess calls avoid shell=True where possible
- [ ] All user inputs validated (URL format, filename chars)
- [ ] Queue file operations use fcntl.flock
- [ ] log.md is append-only (no in-place edits)
- [ ] Git integration for audit trail
- [ ] No network calls except via explicit tools (web_extract, etc.)
- [ ] LLM prompt injection resistant (no eval on prompt fields)

---

## Implementation Order

| Phase | Task | Dependency |
|-------|------|------------|
| 1 | Write behavioral tests (pytest) | None |
| 1.1 | test_frontmatter.py | None |
| 1.2 | test_filename_norm.py | None |
| 1.3 | test_wikilinks.py | None |
| 1.4 | test_index_consistency.py | None |
| 1.5 | test_tag_taxonomy.py | SCHEMA.md |
| 1.6 | test_log_format.py | log.md |
| 1.7 | test_query_relevance.py | Sample pages |
| 1.8 | test_queue_integrity.py | Queue setup |
| 2 | Fix all bugs | Phase 1 tests failing |
| 3 | Red team | Phase 2 fixed |
| 4 | Architecture decisions | Phase 3 clean |
| 5 | Build skill | Phase 4 stable |

---

## Open Questions

1. **Concurrent workers:** Support 1 worker only for now (fcntl safe). Document that multiple workers need queue migration to Redis or similar.

2. **Query answer filing:** Per Karpathy, substantial answers should be filed back to wiki as `queries/` pages. Implement in Phase 4 if user confirms — requires `--confirm` flag since it writes.

3. **YouTube transcript dependency:** `worker.sh` uses `youtube_transcript_api` Python module. Should this be a required dependency or should we use the `felo-youtube-subtitling` skill instead? Recommendation: use skill to avoid dependency.

4. **SCHEMA.md as source of truth:** The tag taxonomy should be machine-readable. Consider adding a YAML section at the top of SCHEMA.md that can be parsed directly, rather than regex-extracting from markdown.

5. **LLM provider:** Currently using `hermes chat` subprocess. Should we support direct API calls (Anthropic, OpenAI) for speed? Recommendation: Hermes subprocess is fine for now, direct API as Phase 6 optimization.

---

## Current Code Issues to Fix (Immediate)

From worker.sh analysis:

1. **Line 167:** `page_name="$subdir/$page_name.md"` — page_name already has `.md` from normalize_filename? Need to trace whether normalize_filename includes extension (it doesn't — line 52 only does tr/dash, no extension). But hermes chat prompt says "create at path.md" and the agent might add `.md` again. **Fix:** Pass just `$subdir/$page_name` without `.md`, and tell agent explicitly: "filename on disk will be `{page_name}.md` — do NOT add extension yourself"

2. **Line 159:** `normalize_filename` only does `tr` operations — no extension handling. So if title is "watch", page_name becomes "watch", then line 167 makes it "concepts/watch.md", but if the agent also appends .md it becomes "concepts/watch.md.md". **Fix:** Pass bare filename to agent, clearly document extension handling.

3. **Tags hardcoded:** Lines 87, 131 use "use SCHEMA.md taxonomy" but agent doesn't actually read SCHEMA. Pre-read taxonomy and pass as explicit list in prompt.

4. **No wikilink validation:** Pass pre-built list of existing page names as constraint.

5. **No index verification post-write:** After hermes chat returns, verify the created file path matches what was written to index.
