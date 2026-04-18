#!/usr/bin/env python3
"""Initialize a new LLM-Wiki vault with base structure."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

VAULT_STRUCTURE = [
    "entities",
    "concepts",
    "comparisons",
    "queries",
    "raw",
    "insights",
    "raw/transcripts",
    "raw/sources",
]

DEFAULT_SCHEMA = """# Schema

## Domain
IT Service Startup Knowledge Base

## Conventions
- Use YAML frontmatter for metadata
- Use wikilinks [[Page Name]] for internal links
- Tag pages with relevant taxonomy tags
- Use page types: concept, entity, comparison, query, summary

## Tag Taxonomy
- Technology: ai, ml, cloud, security, devops
- AI/ML: ai, ml, llm, nlp, computer-vision
- Business: startup, saas, pricing, go-to-market
- Security: zero-trust, security, authentication, encryption
- Operations: monitoring, incident-response, automation

## Thresholds
- Stale content after 90 days
- Oversized page exceeds 200 lines
"""

DEFAULT_INDEX = """# Wiki Index

## Concepts

## Entities

## Comparisons

## Queries

## Raw

## Insights
"""

DEFAULT_LOG = f"""# Activity Log

## {datetime.now().strftime("%Y-%m-%d")} | init | Vault initialized
"""


def create_vault_structure(vault_path: Path) -> list[str]:
    """Create directories and base files."""
    changes = []

    for subdir in VAULT_STRUCTURE:
        dir_path = vault_path / subdir
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            changes.append(f"Created directory: {subdir}/")

    return changes


def init_schema(vault_path: Path) -> list[str]:
    """Create SCHEMA.md with defaults."""
    changes = []
    schema_path = vault_path / "SCHEMA.md"

    if not schema_path.exists():
        schema_path.write_text(DEFAULT_SCHEMA)
        changes.append("Created SCHEMA.md")

    return changes


def init_index(vault_path: Path) -> list[str]:
    """Create index.md with defaults."""
    changes = []
    index_path = vault_path / "index.md"

    if not index_path.exists():
        index_path.write_text(DEFAULT_INDEX)
        changes.append("Created index.md")

    return changes


def init_log(vault_path: Path) -> list[str]:
    """Create log.md with init entry."""
    changes = []
    log_path = vault_path / "log.md"

    if not log_path.exists():
        log_path.write_text(DEFAULT_LOG)
        changes.append("Created log.md")

    return changes


def init_queue(vault_path: Path) -> list[str]:
    """Create empty content_queue.json."""
    changes = []
    queue_path = vault_path / "content_queue.json"

    if not queue_path.exists():
        import json

        queue_path.write_text(json.dumps([], indent=2))
        changes.append("Created content_queue.json")

    return changes


def check_vault_exists(vault_path: Path) -> bool:
    """Check if vault is already initialized."""
    required = [
        vault_path / "SCHEMA.md",
        vault_path / "index.md",
        vault_path / "log.md",
    ]
    return all(p.exists() for p in required)


def init_vault(vault_path: Path, force: bool = False) -> list[str]:
    """Initialize vault with all base structure. Returns list of changes."""
    if not vault_path.exists():
        vault_path.mkdir(parents=True)

    if check_vault_exists(vault_path) and not force:
        return ["Vault already initialized (use --force to reinitialize)"]

    changes = []
    changes.extend(create_vault_structure(vault_path))
    changes.extend(init_schema(vault_path))
    changes.extend(init_index(vault_path))
    changes.extend(init_log(vault_path))
    changes.extend(init_queue(vault_path))

    return changes


def main():
    parser = argparse.ArgumentParser(description="Initialize a new LLM-Wiki vault")
    parser.add_argument(
        "--vault",
        default=os.environ.get("WIKI_VAULT", str(Path.home() / "library")),
        help="Vault path (default: WIKI_VAULT env var or ~/library)",
    )
    parser.add_argument("--force", action="store_true", help="Reinitialize existing vault")
    args = parser.parse_args()

    vault_path = Path(args.vault)

    if not vault_path.parent.exists():
        print(f"Error: Parent directory does not exist: {vault_path.parent}")
        sys.exit(1)

    changes = init_vault(vault_path, force=args.force)

    if len(changes) == 1 and "already initialized" in changes[0]:
        print(changes[0])
        sys.exit(0)

    print(f"Initialized vault at: {vault_path}")
    print("\nChanges:")
    for item in changes:
        print(f"  {item}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
