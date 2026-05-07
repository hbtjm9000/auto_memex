# System Checkup 2026-04-30

## Context
Post-Fedora 44 upgrade, Hermes v0.11.0. Review of patches and skill relevance.

## Skills Audited

| Skill | Status | Action |
|-------|--------|--------|
| `llm-wiki` | Dead stub | Removed |
| `agentmail` | Empty stub | Removed |
| `himalaya-gmail-setup` | Hardcoded credentials | Patched to use `[SET_IN_ENV]` |
| `google-workspace` | Previously removed | N/A |

## Vault Lint State (Post-Batch-Fix)

| Rule | Issues | Auto-Fix? | Status |
|------|--------|-----------|--------|
| Rule 2 (broken wikilinks) | 0 | ✗ | Fixed: 1555 dead links stripped |
| Rule 4 (frontmatter) | 17 | ✗ | Partial: 150 files + 292 fields added, 17 remain (top-level `-` files) |
| Rule 6 (tag taxonomy) | 0 | ✓ | Fixed: added `uncategorized` to taxonomy |
| Rule 9 (oversized) | 18 | ✗ | Exempt: log/SCHEMA auto-exempted |

**Total remaining:** 37 issues (17 CRITICAL + 2 WARNING + 18 INFO)

## Automation Layers

| Layer | Purpose | Status |
|-------|---------|--------|
| Git post-commit hook | Lint on every commit | ✓ Active |
| File watcher (inotifywait) | Real-time change detection | ✓ Running (PID 9417) |
| Hourly cron | Redundancy | ✗ Removed |

## Monitoring Commands

```bash
# Check watcher status
bash scripts/lint_watcher.sh status

# Run linter manually
python scripts/lint_wiki.py --vault /home/hbtjm/library
python scripts/lint_wiki.py --vault /home/hbtjm/library --fix

# Batch fix remaining issues
python scripts/batch_fix_wiki.py --rule 2   # dead links
python scripts/batch_fix_wiki.py --rule 4   # frontmatter
python scripts/batch_fix_wiki.py --all      # all rules
```

## Remaining Manual Work

### Rule 4 (17 files) — Top-Level Files Missing Frontmatter
Files with names starting with hyphen (`-`) were not processed by batch_fix. Manual inspection needed:
- `-ai-ethics-&-misinformation.md`
- `-cybersecurity-&-fraud.md`
- `-digital-privacy-&-data-misuse.md`
- `ai-infrastructure;-compression-algorithms.md`
- `digitalvulnerabilities&userawareness.md`
- etc.

### Rule 9 (18 pages) — Oversized
Manual split needed for content pages >200 lines. Exempt: `log.md`, `log-*.md`, `SCHEMA.md`.

## System Health
- Fedora 44: ✓
- Hermes v0.11.0: ✓
- Vault path (`/home/hbtjm/library`): ✓
- Linter functional: ✓
- Watcher running: ✓