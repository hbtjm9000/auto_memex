# auto_memex Quickstart Guide

**Getting started with your LLM-powered knowledge base in 5 minutes**

---

## Prerequisites

- Python 3.10+
- Git
- (Optional) Hermes CLI for LLM queries

---

## 1. Clone & Setup

```bash
cd ~/lab
git clone https://github.com/hbtjm9000/auto_memex.git
cd auto_memex

# Install dependencies
pip install pytest pyyaml
```

---

## 2. Configure Vault

Your Obsidian vault lives at `~/library`:

```bash
export WIKI_VAULT=~/library
```

Verify structure exists:
```bash
ls ~/library/
# Should show: SCHEMA.md, index.md, log.md, concepts/, entities/, etc.
```

---

## 3. First Ingest

Queue a YouTube video or article for processing:

```bash
# Enqueue a source
python src/ingest_source.py \
  --url "https://www.youtube.com/watch?v=example" \
  --type concept

# Check queue
python src/queue_manager.py status
```

---

## 4. Process Queue

Run the worker to process queued items:

```bash
bash src/worker.sh
```

This will:
1. Pop a task from the queue
2. Fetch content (transcript/article)
3. Generate summary with LLM
4. Create/update wiki page
5. Log the action

---

## 5. Query Your Knowledge

Ask questions about your accumulated knowledge:

```bash
python src/query_wiki.py "What concepts have I studied about cloud security?"
```

**Note:** Requires Hermes LLM configured. Without it, query returns relevant pages only.

---

## 6. Maintain Vault Health

### Check Health
```bash
python src/lint_wiki.py
```

### Auto-Fix Issues
```bash
python src/lint_wiki.py --fix
```

Auto-fixable issues:
- Missing index entries
- Duplicate index entries  
- Broken wikilinks (if target page exists)
- Tag taxonomy violations (if tag is valid)

### Manual Fixes Needed
- Missing frontmatter (legacy pages)
- Incomplete frontmatter fields
- Empty pages

---

## 7. CI/CD (Contributors)

The project has GitHub Actions CI:

```bash
# Test locally before pushing
act push

# Or just run tests
pytest tests/ -v
```

---

## Common Tasks

### Add a New Page Manually

```markdown
---
title: My New Concept
created: 2026-04-18
updated: 2026-04-18
type: concept
tags: [ai, cloud]
sources: []
---

# My New Concept

Content goes here...

Related: [[Another Concept]]
```

### Search Your Vault

```bash
# Find pages by tag
grep -r "tags:.*cloud" ~/library/concepts/

# Find pages mentioning a concept
grep -r "ai-agents" ~/library/

# Use your skill
search_files pattern="ai.*agent" path=~/library
```

### Update SCHEMA.md

Adding a new tag:
1. Open `~/library/SCHEMA.md`
2. Add tag to appropriate category in Tag Taxonomy
3. Save
4. Re-run lint to verify

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `SCHEMA.md not found` | Set `WIKI_VAULT=~/library` |
| Queue stuck | Check `~/library/content_queue.json` for malformed JSON |
| Worker fails on YouTube | Install `youtube-transcript-api` or use felo skill |
| Tag errors | Add tag to SCHEMA.md taxonomy first |
| CI fails locally | Run `ruff check --fix src/ tests/` |

---

## Next Steps

1. **Daily**: Run `worker.sh` to process queued sources
2. **Weekly**: Run `lint_wiki.py --fix` to maintain health
3. **Monthly**: Review `orient_wiki.py` summary for gaps

---

## Resources

- Full skill: `skill_view('auto_memex')`
- CI status: https://github.com/hbtjm9000/auto_memex/actions
- Karpathy's original: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
