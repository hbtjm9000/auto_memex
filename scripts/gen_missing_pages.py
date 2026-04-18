#!/usr/bin/env python3
import re
from pathlib import Path

VAULT = Path("/home/hbtjm/library")
INDEX_PATH = VAULT / "index.md"


def extract_links_from_index(content):
    """Return dict: section -> list of link texts"""
    sections = {}
    current_section = None
    for line in content.splitlines():
        # Match section headers: ## SectionName
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            current_section = m.group(1).strip()
            sections[current_section] = []
            continue
        # Match wikilinks: - [[link]]
        if current_section and line.strip().startswith("- [["):
            # Extract link text
            link_match = re.search(r"\[\[([^\]]+)\]\]", line)
            if link_match:
                link = link_match.group(1).strip()
                sections[current_section].append(link)
    return sections


def link_to_filename(link):
    """Convert link text to a filename (lowercase, hyphens, no spaces)."""
    # Already in the format used in wikilinks? They appear as they are.
    # We'll just lower case and replace spaces with hyphens.
    # But note some links already have hyphens and underscores.
    # We'll keep as is but ensure lowercase and replace spaces with hyphens.
    link = link.strip()
    # Replace spaces with hyphens
    link = link.replace(" ", "-")
    # Convert to lowercase
    link = link.lower()
    # Remove any non-alphanumeric, hyphen, underscore? We'll keep hyphens and underscores.
    # But we want to avoid double hyphens.
    link = re.sub(r"[^a-z0-9_-]", "", link)
    # Collapse multiple hyphens/underscores? Not necessary.
    return link + ".md"


def get_frontmatter(title, page_type, tags=None):
    if tags is None:
        tags = []
    lines = [
        "---",
        f"title: {title}",
        f"created: {Path().cwd()}",  # placeholder, we'll replace with today's date
        f"updated: {Path().cwd()}",
        f"type: {page_type}",
        "tags:",
    ]
    for tag in tags:
        lines.append(f"  - {tag}")
    lines.append("---")
    return "\n".join(lines)


def main():
    content = INDEX_PATH.read_text()
    sections = extract_links_from_index(content)
    print("Sections found:", list(sections.keys()))
    # Map section name to page type (lowercase, singular)
    section_to_type = {
        "Entities": "entity",
        "Concepts": "concept",
        "Comparisons": "comparison",
        "Queries": "query",
        # Additional sections that might appear
        "Summary": "summary",
        "Transcript": "transcript",
        "Raw": "raw",
        "Insight": "insight",
    }
    today = "2026-04-18"  # hardcoded for now, could get from system
    created_count = 0
    for section, links in sections.items():
        page_type = section_to_type.get(section, "concept")  # default
        # Determine subdirectory based on type
        subdir_map = {
            "entity": "entities",
            "concept": "concepts",
            "comparison": "comparisons",
            "query": "queries",
            "summary": "",  # maybe root?
            "transcript": "raw",  # transcripts go in raw/transcripts? but we'll put in raw for now
            "raw": "raw",
            "insight": "insights",
        }
        subdir = subdir_map.get(page_type, "")
        for link in links:
            filename = link_to_filename(link)
            if subdir:
                target_dir = VAULT / subdir
                target_dir.mkdir(exist_ok=True)
                target_path = target_dir / filename
            else:
                target_path = VAULT / filename
            if target_path.exists():
                print(f"Skipping existing: {target_path}")
                continue
            # Determine tags: we could extract from SCHEMA.md taxonomy, but for now empty.
            tags = []
            title = link.replace("-", " ").title()  # rough conversion
            frontmatter = get_frontmatter(title, page_type, tags)
            # Replace date placeholders
            frontmatter = frontmatter.replace("{Path().cwd()}", today)
            target_path.write_text(frontmatter + "\n\n# {title}\n\nTODO: Add content.\n")
            print(f"Created: {target_path}")
            created_count += 1
    print(f"Created {created_count} missing pages.")


if __name__ == "__main__":
    main()
