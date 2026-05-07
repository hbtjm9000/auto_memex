#!/usr/bin/env python3
"""
batch_fix_wiki.py - Batch fix lint issues in the vault

Usage:
    python3 batch_fix_wiki.py --rule 2    # Delete dead wikilinks
    python3 batch_fix_wiki.py --rule 4    # Add missing frontmatter fields
    python3 batch_fix_wiki.py --rule 9    # Report oversized pages (manual split needed)
    python3 batch_fix_wiki.py --all       # Run all auto-fixable rules (2 + 4)
    python3 batch_fix_wiki.py --dry-run   # Show what would change without modifying

Rules:
    Rule 2: Delete dead wikilinks (removes [[ ]] syntax, keeps text)
    Rule 4: Add missing frontmatter fields with sensible defaults
    Rule 9: Generate split report for oversized pages (no auto-fix)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Configuration
VAULT_PATH = Path(os.environ.get("WIKI_VAULT", Path.home() / "library"))
SCHEMA_PATH = VAULT_PATH / "SCHEMA.md"
EXEMPT_DIRS = {"raw", "queries", "comparisons", "insights", "_archive"}

# Frontmatter defaults
DEFAULT_TYPE = "entity"
DEFAULT_TAGS = ["uncategorized"]
REQUIRED_FRONTMATTER = {"title", "created", "updated", "type", "tags"}
VALID_TYPES = {
    "entity", "concept", "comparison", "query", "summary", "transcript",
    "index", "schema", "log", "raw", "insight"
}


def scan_vault(vault_path: Path) -> list[Path]:
    """Find all .md files in the vault, excluding .obsidian."""
    md_files = []
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "_archive"]
        for f in files:
            if f.endswith(".md"):
                md_files.append(Path(root) / f)
    return sorted(md_files)


def is_exempt(file_path: Path, vault_path: Path) -> bool:
    """Check if file is in an exempt directory."""
    rel_path = file_path.relative_to(vault_path)
    return any(part in EXEMPT_DIRS for part in rel_path.parts)


def get_file_stems(files: list[Path], vault_path: Path) -> set[str]:
    """Get normalized stems of all files."""
    stems = set()
    for f in files:
        if is_exempt(f, vault_path):
            continue
        stem = f.stem.replace(" ", "_").replace("-", "_").lower().replace("_", "-")
        stems.add(stem)
    return stems


def wikilink_target(link_text: str) -> str:
    """Normalize a wikilink target."""
    if link_text.lower().endswith(".md"):
        link_text = link_text[:-3]
    if "/" in link_text:
        link_text = link_text.split("/")[-1]
    normalized = link_text.strip().replace(" ", "_").replace("-", "_").lower()
    return normalized.replace("_", "-")


def parse_frontmatter(content: str) -> tuple[dict | None, int, str]:
    """Parse YAML frontmatter. Returns (dict, end_line, rest_of_content)."""
    if not content.startswith("---"):
        return None, 0, content

    lines = content.split("\n")
    end_line = 1

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_line = i
            break
    else:
        return None, 0, content

    _fm_text = "\n".join(lines[1:end_line])
    fm = {}

    for line in lines[1:end_line]:
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")

        if key == "tags":
            match = re.search(r"\[([^\]]*)\]", value)
            if match:
                tags_str = match.group(1)
                fm[key] = [t.strip().strip("\"'") for t in tags_str.split(",") if t.strip()]
            else:
                fm[key] = []
        else:
            fm[key] = value

    rest = "\n".join(lines[end_line + 1:])
    return fm, end_line, rest


def fix_rule_2(files: list[Path], vault_path: Path, dry_run: bool = False) -> dict:
    """
    Rule 2: Delete dead wikilinks.
    Removes [[ ]] syntax from links that don't target existing pages.
    Keeps the link text for context.
    """
    stems = get_file_stems(files, vault_path)
    stats = {"files_modified": 0, "links_removed": 0, "changes": []}

    pattern = re.compile(r"\[\[([^\]]+)\]\]")

    for f in files:
        if is_exempt(f, vault_path):
            continue

        try:
            content = f.read_text()
        except Exception as e:
            print(f"  Skip {f}: {e}")
            continue

        new_content = content
        file_changes = []

        for match in pattern.finditer(content):
            link_text = match.group(1)
            target = wikilink_target(link_text)

            # Check if target exists
            target_variants = {target, target.replace("-", "_"), target.replace("_", "-")}
            if not (target_variants & stems):
                # Dead link - remove [[ ]] but keep text
                replacement = link_text
                new_content = new_content.replace(match.group(0), replacement, 1)
                file_changes.append(f"[[{link_text}]] → {link_text}")
                stats["links_removed"] += 1

        if file_changes:
            stats["files_modified"] += 1
            stats["changes"].append({"file": str(f.relative_to(vault_path)), "changes": file_changes})

            if not dry_run:
                f.write_text(new_content)
                print(f"  Fixed {f.relative_to(vault_path)}: {len(file_changes)} links")

    return stats


def fix_rule_4(files: list[Path], vault_path: Path, dry_run: bool = False) -> dict:
    """
    Rule 4: Add missing frontmatter fields.
    Adds defaults for missing required fields.
    """
    stats = {"files_modified": 0, "fields_added": 0, "changes": []}
    today = datetime.now().strftime("%Y-%m-%d")

    for f in files:
        if is_exempt(f, vault_path):
            continue

        # Skip index, schema, log
        if f.stem.lower() in {"index", "schema", "log"}:
            continue

        try:
            content = f.read_text()
        except Exception as e:
            print(f"  Skip {f}: {e}")
            continue

        fm, end_line, rest = parse_frontmatter(content)
        file_changes = []

        if fm is None:
            # No frontmatter - create it
            title = f.stem.replace("-", " ").replace("_", " ").title()
            new_fm = {
                "title": title,
                "created": today,
                "updated": today,
                "type": DEFAULT_TYPE,
                "tags": DEFAULT_TAGS
            }
            fm_text = "---\n" + "\n".join(f"{k}: {v if k != 'tags' else '[' + ', '.join(v) + ']'}" for k, v in new_fm.items()) + "\n---\n"
            new_content = fm_text + rest
            file_changes = ["Created frontmatter with all fields"]
            stats["fields_added"] += 5

        else:
            # Has frontmatter - check for missing fields
            new_fm = fm.copy()

            if "title" not in fm or not fm["title"]:
                new_fm["title"] = f.stem.replace("-", " ").replace("_", " ").title()
                file_changes.append(f"Added title: {new_fm['title']}")

            if "created" not in fm or not fm["created"]:
                # Try to get file creation time
                try:
                    ctime = datetime.fromtimestamp(f.stat().st_ctime).strftime("%Y-%m-%d")
                except Exception:
                    ctime = today
                new_fm["created"] = ctime
                file_changes.append(f"Added created: {ctime}")

            if "updated" not in fm or not fm["updated"]:
                new_fm["updated"] = today
                file_changes.append(f"Added updated: {today}")

            if "type" not in fm or not fm["type"]:
                new_fm["type"] = DEFAULT_TYPE
                file_changes.append(f"Added type: {DEFAULT_TYPE}")
            elif fm["type"] not in VALID_TYPES:
                new_fm["type"] = DEFAULT_TYPE
                file_changes.append(f"Fixed invalid type: {fm['type']} → {DEFAULT_TYPE}")

            if "tags" not in fm or not fm["tags"]:
                new_fm["tags"] = DEFAULT_TAGS
                file_changes.append(f"Added tags: {DEFAULT_TAGS}")

            if not file_changes:
                continue

            stats["fields_added"] += len(file_changes)

            # Rebuild frontmatter
            fm_text = "---\n" + "\n".join(f"{k}: {v if k != 'tags' else '[' + ', '.join(v) + ']'}" for k, v in new_fm.items()) + "\n---\n"
            new_content = fm_text + rest

        if file_changes:
            stats["files_modified"] += 1
            stats["changes"].append({"file": str(f.relative_to(vault_path)), "changes": file_changes})

            if not dry_run:
                f.write_text(new_content)
                print(f"  Fixed {f.relative_to(vault_path)}: {len(file_changes)} fields")

    return stats


def fix_rule_9(files: list[Path], vault_path: Path, dry_run: bool = False) -> dict:
    """
    Rule 9: Report oversized pages.
    Does NOT auto-fix - generates a report for manual splitting.
    """
    # Get threshold from SCHEMA.md
    threshold = 200
    if SCHEMA_PATH.exists():
        schema_content = SCHEMA_PATH.read_text()
        match = re.search(r"exceeds?\s*~?(\d+)\s*lines?", schema_content, re.IGNORECASE)
        if match:
            threshold = int(match.group(1))

    stats = {"oversized_count": 0, "reports": []}

    for f in files:
        if is_exempt(f, vault_path):
            continue

        try:
            content = f.read_text()
        except Exception:
            continue

        line_count = len(content.split("\n"))

        if line_count > threshold:
            stats["oversized_count"] += 1

            # Find H2 headings as potential split points
            h2_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
            headings = [(m.start(), m.group(1)) for m in h2_pattern.finditer(content)]

            report = {
                "file": str(f.relative_to(vault_path)),
                "lines": line_count,
                "threshold": threshold,
                "excess": line_count - threshold,
                "split_points": headings
            }
            stats["reports"].append(report)

            print(f"  {f.relative_to(vault_path)}: {line_count} lines (excess: {line_count - threshold})")
            if headings:
                print(f"    Split points: {[h[1] for h in headings[:5]]}{'...' if len(headings) > 5 else ''}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Batch fix wiki lint issues")
    parser.add_argument("--rule", type=int, choices=[2, 4, 9], help="Rule to fix")
    parser.add_argument("--all", action="store_true", help="Run all auto-fixable rules (2 + 4)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying")
    args = parser.parse_args()

    if not args.rule and not args.all:
        parser.print_help()
        sys.exit(1)

    print(f"Vault: {VAULT_PATH}")
    print("Scanning files...")

    files = scan_vault(VAULT_PATH)
    print(f"Found {len(files)} markdown files\n")

    if args.dry_run:
        print("=== DRY RUN - No changes will be made ===\n")

    total_stats = {}

    if args.all or args.rule == 2:
        print("Rule 2: Deleting dead wikilinks...")
        stats = fix_rule_2(files, VAULT_PATH, args.dry_run)
        print(f"  Files modified: {stats['files_modified']}")
        print(f"  Links removed: {stats['links_removed']}\n")
        total_stats["rule_2"] = stats

    if args.all or args.rule == 4:
        print("Rule 4: Adding missing frontmatter fields...")
        stats = fix_rule_4(files, VAULT_PATH, args.dry_run)
        print(f"  Files modified: {stats['files_modified']}")
        print(f"  Fields added: {stats['fields_added']}\n")
        total_stats["rule_4"] = stats

    if args.all or args.rule == 9:
        print("Rule 9: Reporting oversized pages...")
        stats = fix_rule_9(files, VAULT_PATH, args.dry_run)
        print(f"  Oversized pages: {stats['oversized_count']}\n")
        total_stats["rule_9"] = stats

    # Summary
    print("=== SUMMARY ===")
    for rule, stats in total_stats.items():
        if rule == "rule_9":
            print(f"Rule {rule[-1]}: {stats['oversized_count']} pages need manual splitting")
        else:
            print(f"Rule {rule[-1]}: {stats['files_modified']} files, {stats.get('links_removed', stats.get('fields_added', 0))} changes")

    if args.dry_run:
        print("\nRe-run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
