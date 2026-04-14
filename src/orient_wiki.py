#!/usr/bin/env python3
"""
orient_wiki.py - Read-only Obsidian vault orientation summary

Produces a structured, read-only summary of the vault state:
- Domain + conventions from SCHEMA.md
- Page inventory from index.md
- Recent activity from log.md (last 20 entries)
- File counts per directory

Exit code: 0 always (idempotent read operation)
"""

import sys
import re
from pathlib import Path
from datetime import datetime

VAULT_ROOT = Path("/home/hbtjm/library")
SCHEMA_PATH = VAULT_ROOT / "SCHEMA.md"
INDEX_PATH = VAULT_ROOT / "index.md"
LOG_PATH = VAULT_ROOT / "log.md"
SUBDIRS = ["entities", "concepts", "comparisons", "queries", "raw", "insights"]


def read_file(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"[Error reading {path}: {e}]"


def extract_yaml_field(content: str, field: str) -> str:
    """Extract value from YAML frontmatter block."""
    match = re.search(rf"^{field}:\s*(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_log_entries(content: str, limit: int = 20) -> list[tuple[str, str, str]]:
    """Parse log.md into (date, action, details) tuples."""
    entries = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: YYYY-MM-DD | action | details
        parts = line.split("|")
        if len(parts) >= 3:
            date = parts[0].strip()
            action = parts[1].strip()
            details = "|".join(parts[2:]).strip()
            entries.append((date, action, details))
    return entries[-limit:]


def count_files() -> dict[str, int]:
    counts = {}
    for d in SUBDIRS:
        dir_path = VAULT_ROOT / d
        if dir_path.is_dir():
            # Recursive count to handle nested dirs (e.g., raw/transcripts/)
            counts[d] = len(list(dir_path.rglob("*.md")))
        else:
            counts[d] = 0
    counts["root"] = 2  # SCHEMA.md + index.md
    return counts


def main() -> int:
    print("=" * 60)
    print("OBSIDIAN VAULT ORIENTATION SUMMARY")
    print(f"Vault: {VAULT_ROOT}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # --- Domain + Conventions from SCHEMA.md ---
    schema_content = read_file(SCHEMA_PATH)
    if schema_content:
        domain_match = re.search(r"## Domain\s*(.+?)(?=\n##|\Z)", schema_content, re.DOTALL)
        domain = domain_match.group(1).strip() if domain_match else "Not defined"
        conventions = []
        for line in schema_content.splitlines():
            if line.strip().startswith("- "):
                conventions.append(line.strip().lstrip("- ").strip())
        print(f"\n[DOMAIN] {domain}")
        print(f"\n[CONVENTIONS]")
        for c in conventions[:8]:
            print(f"  - {c}")
    else:
        print("\n[WARNING] SCHEMA.md not found")

    # --- Page inventory from index.md ---
    index_content = read_file(INDEX_PATH)
    print(f"\n[INDEX STATUS]")
    if index_content:
        # Extract the "Total pages: N" from index
        total_match = re.search(r"Total pages:\s*(\d+)", index_content)
        total = total_match.group(1) if total_match else "?"
        print(f"  index.md exists, reports {total} pages")
        # List sections found in index
        sections = re.findall(r"^##\s+(\w+)", index_content, re.MULTILINE)
        if sections:
            print(f"  Sections: {', '.join(sections)}")
    else:
        print("  index.md is empty or missing")

    # --- File counts ---
    print(f"\n[FILE COUNTS]")
    counts = count_files()
    for d, c in counts.items():
        print(f"  {d}/: {c} .md files")
    print(f"  Total: {sum(counts.values())} .md files")

    # --- Recent activity from log.md ---
    print(f"\n[RECENT ACTIVITY]")
    log_content = read_file(LOG_PATH)
    if log_content:
        entries = parse_log_entries(log_content, 20)
        if entries:
            print(f"  Last {len(entries)} of {len(log_content.splitlines())} log entries:")
            for date, action, details in entries:
                detail_str = details[:60] + "..." if len(details) > 60 else details
                print(f"  [{date}] {action}: {detail_str}")
        else:
            print("  log.md exists but contains no parseable entries")
    else:
        print("  log.md not found or empty (no activity logged yet)")

    # --- Vault state summary ---
    print(f"\n[VAULT STATE]")
    print(f"  Directories: {len([d for d in SUBDIRS if (VAULT_ROOT/d).is_dir()])} configured")
    print(f"  Empty dirs: {', '.join(d for d in SUBDIRS if (VAULT_ROOT/d).is_dir() and counts.get(d, 0) == 0) or 'none'}")
    print(f"  index.md populated: {'yes' if 'Entities' in index_content or 'Concepts' in index_content else 'no'}")
    print(f"  log.md exists: {'yes' if log_content else 'no'}")

    print("\n" + "=" * 60)
    print("Read-only operation complete. Exit code: 0")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
