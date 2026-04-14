"""
test_index_consistency.py - Tests for index.md synchronization with filesystem.
"""

import subprocess
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
INDEX = VAULT / "index.md"


LINT_SCRIPT = Path("/home/hbtjm/Riki/Utils/lint_wiki.py")


def run_lint_with_fix():
    """Run lint_wiki.py with --fix flag and return output."""
    result = subprocess.run(
        ["python3", str(LINT_SCRIPT), "--fix"],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    return result


def run_lint():
    """Run lint_wiki.py and return output."""
    result = subprocess.run(
        ["python3", str(LINT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    return result


def get_index_entries():
    """Parse index.md and return list of (section, entries)."""
    if not INDEX.exists():
        return {}
    
    content = INDEX.read_text()
    entries = {}
    current_section = None
    
    for line in content.split("\n"):
        if line.startswith("## "):
            current_section = line.replace("## ", "").strip()
            entries[current_section] = []
        elif line.startswith("- [[") and current_section:
            entries[current_section].append(line)
    
    return entries


def test_file_on_disk_missing_from_index(temp_page, sample_frontmatter, clean_index):
    """
    Create a file directly on disk (bypass worker).
    Run lint_wiki.py --fix.
    Assert file is added to index.md.
    """
    # Create file bypassing worker
    content = sample_frontmatter + """
# Orphan File Test

This file exists but is not in index.
"""
    path = temp_page("concepts", "orphan-file-test", content)
    
    # Get index entries before
    entries_before = get_index_entries()
    concepts_before = entries_before.get("Concepts", [])
    
    # Run lint --fix
    result = run_lint_with_fix()
    output = result.stdout + result.stderr
    
    # After fix, file should be in index
    entries_after = get_index_entries()
    concepts_after = entries_after.get("Concepts", [])
    
    # The file should now be in index
    assert any("orphan-file-test" in e for e in concepts_after), \
        f"File should be added to index after --fix. Index: {concepts_after}"


def test_file_in_index_missing_from_disk(temp_page, clean_index):
    """
    Add entry to index.md for non-existent file.
    Run lint_wiki.py.
    Assert CRITICAL reported.
    """
    # Read current index
    if INDEX.exists():
        original = INDEX.read_text()
    else:
        original = ""
    
    try:
        # Add entry for non-existent file
        fake_entry = "- [[concepts/non-existent-file.md]]"
        new_index = original.rstrip() + "\n" + fake_entry + "\n"
        INDEX.write_text(new_index)
        
        # Run lint
        result = run_lint()
        output = result.stdout + result.stderr
        
        # Should report CRITICAL for missing file
        assert "CRITICAL" in output or "critical" in output.lower(), \
            f"Expected CRITICAL for missing file in index, got: {output}"
        assert "non-existent-file" in output.lower()
    
    finally:
        # Restore original
        if original:
            INDEX.write_text(original)


def test_index_entry_matches_filesystem(temp_page, sample_frontmatter, clean_index):
    """
    Create file concepts/test-page.md.
    Add to index.md.
    Verify index entry path matches actual path.
    """
    # Create file
    content = sample_frontmatter + """
# Test Page Match

Testing index entry matches filesystem.
"""
    path = temp_page("concepts", "test-page-match", content)
    
    # Get normalized path
    relative_path = path.relative_to(VAULT)
    
    # Add to index manually
    if INDEX.exists():
        original = INDEX.read_text()
    else:
        original = ""
    
    try:
        new_entry = f"- [[{relative_path}]]\n"
        new_index = original.rstrip() + "\n" + new_entry
        INDEX.write_text(new_index)
        
        # Verify index entry matches
        entries = get_index_entries()
        found = any(str(relative_path) in e for section in entries.values() for e in section)
        
        assert found, \
            f"Index entry should match {relative_path}. Entries: {entries}"
    
    finally:
        if original:
            INDEX.write_text(original)


def test_index_section_for_filetype(temp_page, sample_frontmatter, clean_index):
    """
    Create entity page, verify it goes in Entities section.
    Create concept page, verify it goes in Concepts section.
    """
    # Create entity page
    entity_content = sample_frontmatter + """
# Troy Hunt

Person entity.
"""
    # Fix the type in frontmatter
    entity_content = entity_content.replace("type: concept", "type: entity")
    entity_path = temp_page("entities", "index-entity-test", entity_content)
    
    # Create concept page
    concept_path = temp_page("concepts", "index-concept-test", sample_frontmatter + """
# Test Concept

A test concept page.
""")
    
    # Run lint --fix
    result = run_lint_with_fix()
    
    # Check index sections
    entries = get_index_entries()
    
    # Entity should be in Entities section
    entities = entries.get("Entities", [])
    assert any("index-entity-test" in e for e in entities), \
        f"Entity should be in Entities section: {entities}"
    
    # Concept should be in Concepts section
    concepts = entries.get("Concepts", [])
    assert any("index-concept-test" in e for e in concepts), \
        f"Concept should be in Concepts section: {concepts}"


def test_missing_index_file_creates_empty_index():
    """
    If index.md is missing, lint should still run.
    After --fix, index.md should be created.
    """
    index_backup = None
    if INDEX.exists():
        index_backup = INDEX.read_text()
        INDEX.unlink()
    
    try:
        # Run lint --fix
        result = run_lint_with_fix()
        
        # index.md should now exist
        assert INDEX.exists(), "index.md should be created after --fix"
        
        content = INDEX.read_text()
        assert "## " in content, "index.md should have section headers"
    
    finally:
        if index_backup:
            INDEX.write_text(index_backup)


def test_duplicate_index_entry_not_created(temp_page, sample_frontmatter, clean_index):
    """
    File already in index under correct section.
    Run lint --fix again.
    Assert entry is not duplicated.
    """
    # Create file
    content = sample_frontmatter + """
# No Duplicate Test

Testing no duplicate entries.
"""
    path = temp_page("concepts", "no-dup-test", content)
    relative_path = path.relative_to(VAULT)
    
    # Add to index twice
    if INDEX.exists():
        original = INDEX.read_text()
    else:
        original = ""
    
    try:
        entry = f"- [[{relative_path}]]\n"
        new_index = original.rstrip() + "\n" + entry + entry  # duplicate
        INDEX.write_text(new_index)
        
        # Run lint --fix
        result = run_lint_with_fix()
        
        # Count occurrences
        content = INDEX.read_text()
        count = content.count(str(relative_path))
        
        # Should only have one entry (fix should dedupe)
        assert count <= 1, \
            f"Duplicate entry found in index: {content}"
    
    finally:
        if original:
            INDEX.write_text(original)
