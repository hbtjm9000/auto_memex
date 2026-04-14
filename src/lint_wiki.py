#!/usr/bin/env python3
"""
lint_wiki.py - Obsidian Vault Linter

Lints the Obsidian vault at /home/hbtjm/library for wiki hygiene issues.
Modular architecture following the wiki build plan.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

# =============================================================================
# Configuration
# =============================================================================

VAULT_PATH = Path("/home/hbtjm/library")
SCHEMA_PATH = VAULT_PATH / "SCHEMA.md"
INDEX_PATH = VAULT_PATH / "index.md"
LOG_PATH = VAULT_PATH / "log.md"

# Directories that are exempt from orphan detection
EXEMPT_DIRS = {"raw", "queries", "comparisons", "insights"}
HUB_PAGES = {"index", "readme"}

# Required frontmatter fields
REQUIRED_FRONTMATTER = {"title", "created", "updated", "type", "tags"}

# Valid page types
VALID_TYPES = {"entity", "concept", "comparison", "query", "summary"}

# Auto-fixable rules (1-indexed as per spec)
AUTO_FIXABLE_RULES = {1, 2, 3, 5, 6}

# =============================================================================
# Data Structures
# =============================================================================

class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

@dataclass
class Issue:
    rule: int
    severity: Severity
    message: str
    file_path: Optional[Path] = None
    line: Optional[int] = None
    fix_available: bool = False

    def __lt__(self, other):
        order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
        return (order[self.severity], self.rule) < (order[other.severity], other.rule)

@dataclass
class ScanResult:
    issues: list[Issue] = field(default_factory=list)
    total_files: int = 0
    files_with_issues: int = 0

    def add_issue(self, issue: Issue):
        self.issues.append(issue)
        if issue.file_path:
            self.files_with_issues = len(set(i.file_path for i in self.issues if i.file_path))

    @property
    def clean(self) -> bool:
        return len(self.issues) == 0

# =============================================================================
# Schema Parser
# =============================================================================

@dataclass
class SchemaConfig:
    tag_taxonomy: set[str] = field(default_factory=set)
    stale_days: int = 90
    oversized_threshold: int = 200

def parse_schema(schema_path: Path) -> SchemaConfig:
    """Parse SCHEMA.md to extract tag taxonomy and thresholds."""
    config = SchemaConfig()
    
    if not schema_path.exists():
        print(f"Warning: {schema_path} not found, using defaults", file=sys.stderr)
        return config
    
    content = schema_path.read_text()
    
    # Extract tag taxonomy
    taxonomy_section = re.search(r"## Tag Taxonomy\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if taxonomy_section:
        taxonomy_text = taxonomy_section.group(1)
        # Extract tags from lines like: - Technology: ai, ml, cloud, security...
        tag_lines = re.findall(r"^\s*-\s*(?:[^:]+):\s*(.+)$", taxonomy_text, re.MULTILINE)
        for line in tag_lines:
            tags = re.findall(r'\b([a-z][a-z0-9-]*)\b', line.lower())
            config.tag_taxonomy.update(tags)
    
    # Extract stale_days threshold
    stale_match = re.search(r"stale.*?(\d+)\s*days?", content, re.IGNORECASE)
    if stale_match:
        config.stale_days = int(stale_match.group(1))
    
    # Extract oversized threshold
    size_match = re.search(r"exceeds?\s*~?(\d+)\s*lines?", content, re.IGNORECASE)
    if size_match:
        config.oversized_threshold = int(size_match.group(1))
    
    return config

# =============================================================================
# Scanner
# =============================================================================

def scan_vault(vault_path: Path) -> list[Path]:
    """Find all .md files in the vault, excluding .obsidian."""
    md_files = []
    for root, dirs, files in os.walk(vault_path):
        # Skip .obsidian and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                md_files.append(Path(root) / f)
    return sorted(md_files)

# =============================================================================
# Link Graph
# =============================================================================

@dataclass
class LinkGraph:
    outbound: dict[Path, set[str]] = field(default_factory=dict)
    inbound: dict[str, set[Path]] = field(default_factory=dict)
    all_targets: set[str] = field(default_factory=set)

def wikilink_target(link_text: str) -> str:
    """Normalize a wikilink target for comparison.
    
    Handles spaces by converting to underscores and lowercasing.
    [[Data Breaches]] -> data_breaches -> data-breaches
    """
    # Remove namespace prefix if present
    if '/' in link_text:
        link_text = link_text.split('/')[-1]
    # Normalize: spaces -> underscores -> hyphens, lowercase
    normalized = link_text.strip().replace(' ', '_').replace('-', '_').lower()
    # Convert underscores back to hyphens for canonical form
    return normalized.replace('_', '-')

def parse_wikilinks(content: str) -> set[str]:
    """Extract all [[wikilinks]] from content."""
    pattern = r'\[\[([^\]]+)\]\]'
    links = set()
    for match in re.finditer(pattern, content):
        link_text = match.group(1)
        links.add(wikilink_target(link_text))
    return links

def build_link_graph(files: list[Path], vault_path: Path) -> LinkGraph:
    """Build a graph of wikilinks between pages."""
    graph = LinkGraph()
    
    # First pass: collect all potential targets from filenames
    for f in files:
        rel_path = f.relative_to(vault_path)
        # Extract the stem (filename without extension)
        stem = rel_path.stem
        # Normalize: spaces -> underscores -> hyphens
        normalized = stem.replace(' ', '_').replace('-', '_').lower().replace('_', '-')
        graph.all_targets.add(normalized)
    
    # Second pass: extract wikilinks from content
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        links = parse_wikilinks(content)
        graph.outbound[f] = links
        
        for link in links:
            if link not in graph.inbound:
                graph.inbound[link] = set()
            graph.inbound[link].add(f)
    
    return graph

# =============================================================================
# Frontmatter Parser
# =============================================================================

@dataclass
class Frontmatter:
    title: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    page_type: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    raw_content: str = ""

def parse_frontmatter(content: str) -> tuple[Optional[Frontmatter], int]:
    """Parse YAML frontmatter from content.
    
    Returns (Frontmatter, end_line) or (None, 0) if no frontmatter.
    """
    if not content.startswith('---'):
        return None, 0
    
    lines = content.split('\n')
    end_line = 1  # Start after first ---
    
    # Find closing ---
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_line = i
            break
    else:
        return None, 0
    
    fm_text = '\n'.join(lines[1:end_line])
    fm = Frontmatter(raw_content=fm_text)
    
    # Parse fields
    for line in lines[1:end_line]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # title: value
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip().strip('"\'')
            
            if key == 'title':
                fm.title = value
            elif key == 'created':
                fm.created = value
            elif key == 'updated':
                fm.updated = value
            elif key == 'type':
                fm.page_type = value
            elif key == 'tags':
                # Parse [tag1, tag2, tag3] or [tag1,tag2]
                match = re.search(r'\[([^\]]*)\]', value)
                if match:
                    tags_str = match.group(1)
                    fm.tags = [t.strip().strip('"\'') for t in tags_str.split(',') if t.strip()]
            elif key == 'sources':
                match = re.search(r'\[([^\]]*)\]', value)
                if match:
                    sources_str = match.group(1)
                    fm.sources = [s.strip().strip('"\'') for s in sources_str.split(',') if s.strip()]
            elif key == 'contradictions':
                match = re.search(r'\[([^\]]*)\]', value)
                if match:
                    contrad_str = match.group(1)
                    fm.contradictions = [c.strip().strip('"\'') for c in contrad_str.split(',') if c.strip()]
    
    return fm, end_line

# =============================================================================
# Rule Implementations
# =============================================================================

def check_orphans(files: list[Path], graph: LinkGraph, vault_path: Path) -> list[Issue]:
    """Rule 1: Find pages with 0 inbound wikilinks (excluding exempt dirs)."""
    issues = []
    
    for f in files:
        rel_path = f.relative_to(vault_path)
        
        # Skip exempt directories
        if rel_path.parts[0] in EXEMPT_DIRS:
            continue
        
        # Skip hub pages
        if rel_path.stem.lower() in HUB_PAGES:
            continue
        
        # Check inbound links
        stem = rel_path.stem.replace(' ', '_').replace('-', '_').lower().replace('_', '-')
        inbound = graph.inbound.get(stem, set())
        
        if len(inbound) == 0:
            issues.append(Issue(
                rule=1,
                severity=Severity.WARNING,
                message=f"Orphan page: no inbound wikilinks",
                file_path=f,
                fix_available=False
            ))
    
    return issues

def check_broken_links(files: list[Path], graph: LinkGraph, vault_path: Path) -> list[Issue]:
    """Rule 2: Find [[wikilinks]] to pages that don't exist on disk."""
    issues = []
    
    for f in files:
        outbound = graph.outbound.get(f, set())
        
        for link in outbound:
            # Check if this link targets an existing file
            # Normalize link to check both _ and - variations
            link_variants = {link, link.replace('-', '_'), link.replace('_', '-')}
            
            found = False
            for variant in link_variants:
                # Check if any file stem matches
                for md_file in files:
                    file_stem = md_file.stem.replace(' ', '_').replace('-', '_').lower().replace('_', '-')
                    if file_stem == variant or file_stem == variant.replace('-', '_'):
                        found = True
                        break
                if found:
                    break
            
            if not found:
                issues.append(Issue(
                    rule=2,
                    severity=Severity.CRITICAL,
                    message=f"Broken wikilink: [[{link}]]",
                    file_path=f,
                    fix_available=False
                ))
    
    return issues

def check_index_completeness(files: list[Path], vault_path: Path) -> list[Issue]:
    """Rule 3: Find pages on disk missing from index.md."""
    issues = []
    
    if not INDEX_PATH.exists():
        # If index.md doesn't exist, all pages are missing
        for f in files:
            issues.append(Issue(
                rule=3,
                severity=Severity.CRITICAL,
                message="index.md does not exist",
                file_path=f,
                fix_available=True
            ))
        return issues
    
    index_content = INDEX_PATH.read_text()
    
    # Get all pages
    for f in files:
        rel_path = f.relative_to(vault_path)
        
        # Skip index itself
        if rel_path.stem.lower() == 'index':
            continue
        
        # Check if page is referenced in index
        # Simple check: look for the stem in index content
        stem = rel_path.stem
        if stem.lower() not in index_content.lower():
            issues.append(Issue(
                rule=3,
                severity=Severity.WARNING,
                message=f"Page not found in index.md",
                file_path=f,
                fix_available=True
            ))
    
    return issues

def check_frontmatter_validation(files: list[Path], vault_path: Path) -> list[Issue]:
    """Rule 4: Check for missing required frontmatter fields."""
    issues = []
    
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, end_line = parse_frontmatter(content)
        
        if fm is None:
            issues.append(Issue(
                rule=4,
                severity=Severity.CRITICAL,
                message="Missing frontmatter",
                file_path=f,
                fix_available=False
            ))
            continue
        
        # Check required fields
        missing = []
        for field in REQUIRED_FRONTMATTER:
            if field == 'title' and not fm.title:
                missing.append(field)
            elif field == 'created' and not fm.created:
                missing.append(field)
            elif field == 'updated' and not fm.updated:
                missing.append(field)
            elif field == 'type':
                if not fm.page_type:
                    missing.append(field)
                elif fm.page_type not in VALID_TYPES:
                    issues.append(Issue(
                        rule=4,
                        severity=Severity.WARNING,
                        message=f"Invalid type: '{fm.page_type}'",
                        file_path=f,
                        fix_available=False
                    ))
            elif field == 'tags':
                if not fm.tags:
                    missing.append(field)
        
        if missing:
            issues.append(Issue(
                rule=4,
                severity=Severity.WARNING,
                message=f"Missing frontmatter fields: {', '.join(missing)}",
                file_path=f,
                fix_available=False
            ))
    
    return issues

def check_stale_content(files: list[Path], vault_path: Path, stale_days: int) -> list[Issue]:
    """Rule 5: Find pages with updated date > stale_days old."""
    issues = []
    cutoff = datetime.now() - timedelta(days=stale_days)
    
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, _ = parse_frontmatter(content)
        if not fm or not fm.updated:
            continue
        
        try:
            updated_date = datetime.strptime(fm.updated, "%Y-%m-%d")
        except ValueError:
            try:
                updated_date = datetime.strptime(fm.updated, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        
        if updated_date < cutoff:
            issues.append(Issue(
                rule=5,
                severity=Severity.INFO,
                message=f"Stale content: updated {fm.updated}",
                file_path=f,
                fix_available=True
            ))
    
    return issues

def check_tag_taxonomy(files: list[Path], vault_path: Path, valid_tags: set[str]) -> list[Issue]:
    """Rule 6: Find tags not in SCHEMA.md taxonomy."""
    issues = []
    
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, _ = parse_frontmatter(content)
        if not fm or not fm.tags:
            continue
        
        invalid_tags = [tag for tag in fm.tags if tag.lower() not in valid_tags]
        
        if invalid_tags:
            issues.append(Issue(
                rule=6,
                severity=Severity.WARNING,
                message=f"Tags not in taxonomy: {', '.join(invalid_tags)}",
                file_path=f,
                fix_available=True
            ))
    
    return issues

def check_empty_pages(files: list[Path], vault_path: Path) -> list[Issue]:
    """Rule 7: Find pages with only frontmatter and no content."""
    issues = []
    
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, end_line = parse_frontmatter(content)
        if not fm:
            # If no frontmatter, check if file is essentially empty
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if len(lines) == 0:
                issues.append(Issue(
                    rule=7,
                    severity=Severity.INFO,
                    message="Empty page (no frontmatter, no content)",
                    file_path=f,
                    fix_available=False
                ))
            continue
        
        # Get content after frontmatter
        content_lines = content.split('\n')[end_line+1:]
        content_lines = [l.strip() for l in content_lines if l.strip()]
        
        if len(content_lines) == 0:
            issues.append(Issue(
                rule=7,
                severity=Severity.INFO,
                message="Empty page (frontmatter only, no content)",
                file_path=f,
                fix_available=False
            ))
    
    return issues

def check_contradictions(files: list[Path], vault_path: Path) -> list[Issue]:
    """Rule 8: Find same topic in multiple pages with conflicting claims."""
    issues = []
    
    # This is a no-fix rule - just flag potential contradictions
    # Check for frontmatter flagging
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, _ = parse_frontmatter(content)
        if fm and fm.contradictions:
            issues.append(Issue(
                rule=8,
                severity=Severity.WARNING,
                message=f"Contradictions flagged with: {', '.join(fm.contradictions)}",
                file_path=f,
                fix_available=False
            ))
    
    return issues

def check_oversized_pages(files: list[Path], vault_path: Path, threshold: int) -> list[Issue]:
    """Rule 9: Find pages exceeding line threshold."""
    issues = []
    
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        
        line_count = len(content.split('\n'))
        
        if line_count > threshold:
            issues.append(Issue(
                rule=9,
                severity=Severity.INFO,
                message=f"Oversized page: {line_count} lines (threshold: {threshold})",
                file_path=f,
                fix_available=False
            ))
    
    return issues

# =============================================================================
# Formatter
# =============================================================================

def format_issue(issue: Issue, verbose: bool = False) -> str:
    """Format an issue for output."""
    if verbose and issue.file_path:
        rel_path = issue.file_path.relative_to(VAULT_PATH)
        location = f" [{rel_path}]"
    else:
        location = ""
    
    prefix = f"[{issue.severity.value.upper()}]"
    return f"{prefix} Rule {issue.rule}: {issue.message}{location}"

def format_report(result: ScanResult, verbose: bool = False) -> str:
    """Format the scan result as a report."""
    lines = []
    
    # Group by severity
    by_severity = {Severity.CRITICAL: [], Severity.WARNING: [], Severity.INFO: []}
    for issue in result.issues:
        by_severity[issue.severity].append(issue)
    
    lines.append("=" * 60)
    lines.append("WIKI LINT REPORT")
    lines.append("=" * 60)
    lines.append(f"Total files scanned: {result.total_files}")
    lines.append(f"Files with issues: {result.files_with_issues}")
    lines.append(f"Total issues: {len(result.issues)}")
    lines.append("")
    
    for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO]:
        issues = by_severity[severity]
        if not issues:
            continue
        
        lines.append(f"## {severity.value.upper()} ({len(issues)} issues)")
        lines.append("-" * 40)
        
        for issue in sorted(issues):
            lines.append(f"  • {format_issue(issue, verbose)}")
        lines.append("")
    
    return "\n".join(lines)

# =============================================================================
# Log Writer
# =============================================================================

def append_to_log(result: ScanResult, vault_path: Path) -> None:
    """Append scan results to log.md."""
    log_path = vault_path / "log.md"
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Format the entry
    entry_lines = [
        f"## [{today}] lint | {len(result.issues)} issues found",
    ]
    
    if result.issues:
        by_severity = {Severity.CRITICAL: [], Severity.WARNING: [], Severity.INFO: []}
        for issue in result.issues:
            by_severity[issue.severity].append(issue)
        
        for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO]:
            issues = by_severity[severity]
            if issues:
                entry_lines.append(f"  {severity.value.upper()}: {len(issues)}")
                for issue in sorted(issues)[:5]:  # Limit per severity
                    rel_path = issue.file_path.relative_to(vault_path) if issue.file_path else "unknown"
                    entry_lines.append(f"    - Rule {issue.rule}: {issue.message} [{rel_path}]")
                if len(issues) > 5:
                    entry_lines.append(f"    ... and {len(issues) - 5} more")
    else:
        entry_lines.append("  Clean - no issues found")
    
    entry_lines.append("")  # Empty line at end
    
    entry = "\n".join(entry_lines)
    
    if log_path.exists():
        existing = log_path.read_text()
        log_path.write_text(existing + entry)
    else:
        log_path.write_text(entry)

# =============================================================================
# Auto-Fix Functions
# =============================================================================

def fix_orphans(result: ScanResult, graph: LinkGraph, vault_path: Path) -> list[str]:
    """Auto-fix: Add inbound links to orphan pages."""
    changes = []
    # Note: Orphan pages can't really be auto-fixed without adding content
    # This would require creating new wikilinks, which is content editing
    # We'll just identify them for now
    return changes

def fix_broken_links(result: ScanResult, graph: LinkGraph, vault_path: Path) -> list[str]:
    """Auto-fix: Remove or flag broken wikilinks."""
    changes = []
    # Broken links can't be auto-fixed safely - we can only note them
    return changes

def fix_index_completeness(result: ScanResult, vault_path: Path) -> list[str]:
    """Auto-fix: Add missing pages to index.md."""
    changes = []

    # If index doesn't exist, create it with section headers
    if not INDEX_PATH.exists():
        # Create a minimal index with all section headers
        default_index = """# Wiki Index

## Concepts

## Entities

## Comparisons

## Queries
"""
        INDEX_PATH.write_text(default_index)
        changes.append("Created missing index.md")

    index_content = INDEX_PATH.read_text()

    # Get list of all pages that should be in index
    for issue in result.issues:
        if issue.rule != 3 or not issue.file_path:
            continue

        rel_path = issue.file_path.relative_to(vault_path)
        stem = issue.file_path.stem

        # Check if already in index (more precise check)
        # Look for [[stem]] pattern specifically
        import re
        pattern = re.compile(r'\[\[' + re.escape(stem) + r'(\]|_)', re.IGNORECASE)
        if pattern.search(index_content):
            continue

        # Add to appropriate section based on type
        fm, _ = parse_frontmatter(issue.file_path.read_text())
        page_type = fm.page_type if fm and fm.page_type else "concept"

        # Find insertion point - look for section header
        section_header = f"## {page_type.title()}s"

        # Split content into lines for processing
        lines = index_content.split('\n')
        insert_idx = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section_header:
                # Found section header, insert after its content lines
                insert_idx = i + 1
                # Skip empty lines until next section or list item
                while insert_idx < len(lines):
                    next_line = lines[insert_idx].strip()
                    if next_line.startswith('## ') or (next_line.startswith('- [[') and insert_idx > 0):
                        # Insert before next section or list item
                        break
                    insert_idx += 1
                break

        if insert_idx is not None:
            new_line = f"- [[{stem}]]"
            lines.insert(insert_idx, new_line)
            index_content = '\n'.join(lines)
            changes.append(f"Added to index: {stem}")
        else:
            # Section doesn't exist, create it before Comparisons (or at end)
            # Default to Concepts section if section not found
            new_section = f"\n## {page_type.title()}s\n\n- [[{stem}]]\n"
            if "## Concepts" in index_content:
                # Insert before ## Concepts
                index_content = index_content.replace("## Concepts", new_section + "## Concepts", 1)
            else:
                index_content = index_content.rstrip() + new_section
            changes.append(f"Added to index: {stem} (created section)")

    if changes:
        INDEX_PATH.write_text(index_content)

    return changes

def fix_stale_content(result: ScanResult, vault_path: Path) -> list[str]:
    """Auto-fix: Update the updated date for stale pages."""
    changes = []
    today = datetime.now().strftime("%Y-%m-%d")
    
    for issue in result.issues:
        if issue.rule != 5 or not issue.file_path:
            continue
        
        f = issue.file_path
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, end_line = parse_frontmatter(content)
        if not fm:
            continue
        
        # Update the updated date
        lines = content.split('\n')
        
        # Find and update the updated field
        new_lines = []
        updated_found = False
        for i, line in enumerate(lines):
            if i > 0 and i <= end_line and line.strip().startswith('updated:'):
                new_lines.append(f"updated: {today}")
                updated_found = True
            else:
                new_lines.append(line)
        
        if updated_found:
            new_content = '\n'.join(new_lines)
            # Grep guard for idempotency
            if 'updated: ' + today not in new_content:
                f.write_text(new_content)
                changes.append(f"Updated stale date: {f.stem}")
    
    return changes

def fix_tag_taxonomy(result: ScanResult, valid_tags: set[str]) -> list[str]:
    """Auto-fix: Strip invalid tags."""
    changes = []
    
    for issue in result.issues:
        if issue.rule != 6 or not issue.file_path:
            continue
        
        f = issue.file_path
        try:
            content = f.read_text()
        except Exception:
            continue
        
        fm, end_line = parse_frontmatter(content)
        if not fm or not fm.tags:
            continue
        
        # Filter to valid tags
        valid = [tag for tag in fm.tags if tag.lower() in valid_tags]
        
        if len(valid) != len(fm.tags):
            # Update frontmatter
            lines = content.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                if i > 0 and i <= end_line and line.strip().startswith('tags:'):
                    new_lines.append(f"tags: [{', '.join(valid)}]")
                else:
                    new_lines.append(line)
            
            new_content = '\n'.join(new_lines)
            # Grep guard for idempotency
            tags_line = f"tags: [{', '.join(valid)}]"
            if tags_line not in new_content:
                f.write_text(new_content)
                removed = set(fm.tags) - set(valid)
                changes.append(f"Removed invalid tags from {f.stem}: {', '.join(removed)}")
    
    return changes

# =============================================================================
# Main
# =============================================================================

def run_scan(vault_path: Path, fix_mode: bool = False, verbose: bool = False) -> ScanResult:
    """Run the lint scan."""
    result = ScanResult()
    
    # Parse schema for configuration
    schema = parse_schema(SCHEMA_PATH)
    
    # Scan files
    files = scan_vault(vault_path)
    result.total_files = len(files)
    
    # Build link graph
    graph = build_link_graph(files, vault_path)
    
    # Run all checks
    result.issues.extend(check_orphans(files, graph, vault_path))
    result.issues.extend(check_broken_links(files, graph, vault_path))
    result.issues.extend(check_index_completeness(files, vault_path))
    result.issues.extend(check_frontmatter_validation(files, vault_path))
    result.issues.extend(check_stale_content(files, vault_path, schema.stale_days))
    result.issues.extend(check_tag_taxonomy(files, vault_path, schema.tag_taxonomy))
    result.issues.extend(check_empty_pages(files, vault_path))
    result.issues.extend(check_contradictions(files, vault_path))
    result.issues.extend(check_oversized_pages(files, vault_path, schema.oversized_threshold))
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Obsidian Vault Linter")
    parser.add_argument("--fix", action="store_true", help="Auto-fix fixable issues")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--vault", default=str(VAULT_PATH), help="Vault path")
    parser.add_argument("--no-log", action="store_true", help="Don't append to log.md")
    args = parser.parse_args()
    
    vault_path = Path(args.vault)
    
    # Run scan
    result = run_scan(vault_path, fix_mode=args.fix, verbose=args.verbose)
    
    # Format and print report
    print(format_report(result, verbose=args.verbose))
    
    # Auto-fix if requested
    if args.fix:
        schema = parse_schema(SCHEMA_PATH)
        all_changes = []

        # Build link graph for fix functions
        files = scan_vault(vault_path)
        graph = build_link_graph(files, vault_path)

        # Rule 3: fix index completeness
        index_issues = [i for i in result.issues if i.rule == 3]
        if index_issues:
            changes = fix_index_completeness(ScanResult(issues=index_issues), vault_path)
            all_changes.extend(changes)

        # Rule 5: fix stale content
        stale_issues = [i for i in result.issues if i.rule == 5]
        if stale_issues:
            changes = fix_stale_content(ScanResult(issues=stale_issues), vault_path)
            all_changes.extend(changes)

        # Rule 6: fix tag taxonomy
        tag_issues = [i for i in result.issues if i.rule == 6]
        if tag_issues:
            changes = fix_tag_taxonomy(ScanResult(issues=tag_issues), schema.tag_taxonomy)
            all_changes.extend(changes)

        if all_changes:
            print("\n## CHANGES MADE")
            print("-" * 40)
            for change in all_changes:
                print(f"  {change}")
        else:
            print("\nNo changes needed.")
    
    # Append to log
    if not args.no_log:
        append_to_log(result, vault_path)
    
    # Exit code
    sys.exit(0 if result.clean else 1)

if __name__ == "__main__":
    main()
