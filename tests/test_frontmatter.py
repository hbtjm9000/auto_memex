"""
test_frontmatter.py - Tests for frontmatter validation in lint_wiki.py.
"""

import subprocess
import tempfile
import os
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")


LINT_SCRIPT = Path("/home/hbtjm/Riki/Utils/lint_wiki.py")


def run_lint_vault():
    """Run lint_wiki.py on entire vault and return output."""
    result = subprocess.run(
        ["python3", str(LINT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    return result


def test_missing_frontmatter_is_critical(temp_page, sample_frontmatter):
    """
    Create temp file with no frontmatter.
    Run lint_wiki.py.
    Assert CRITICAL issue raised mentioning required fields.
    """
    # Create file with no frontmatter - just raw content
    content = "# No Frontmatter Here\n\nSome content without YAML block."
    path = temp_page("concepts", "no-frontmatter-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Should report missing frontmatter as CRITICAL
    assert "CRITICAL" in output or "critical" in output.lower(), \
        f"Expected CRITICAL for missing frontmatter, got: {output}"
    # Should mention the required field names
    assert any(field in output for field in ["title", "created", "updated", "type", "tags"]), \
        f"Expected mention of required fields, got: {output}"


def test_valid_frontmatter_no_issue(temp_page, sample_frontmatter):
    """
    Create temp file with all required fields: title, created, updated, type, tags, sources.
    Run lint_wiki.py.
    Assert no CRITICAL issues for that file.
    """
    content = sample_frontmatter + "# Valid Frontmatter\n\nContent with all required fields."
    path = temp_page("concepts", "valid-frontmatter-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # File with complete frontmatter should not have CRITICAL issues mentioning this file
    lines = output.split("\n")
    critical_lines = [l for l in lines if "CRITICAL" in l and "valid-frontmatter-test" in l]
    assert len(critical_lines) == 0, \
        f"Expected no CRITICAL issues for valid frontmatter, got: {critical_lines}"


def test_partial_frontmatter_reports_missing_fields(temp_page):
    """
    Create temp file with only title and type.
    Run lint_wiki.py.
    Assert CRITICAL mentions missing created, updated, tags, sources.
    """
    content = """---
title: Partial Page
type: concept
---

# Partial Frontmatter

Only title and type provided.
"""
    path = temp_page("concepts", "partial-frontmatter-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Should list what's missing
    missing_fields = ["created", "updated", "tags", "sources"]
    found_missing = [f for f in missing_fields if f in output]
    assert len(found_missing) >= 2, \
        f"Expected missing fields to be reported, got: {output}"


def test_frontmatter_requires_yaml_delimiters(temp_page):
    """
    Create file with frontmatter-like content that is NOT properly delimited.
    Assert lint detects this as missing proper frontmatter.
    """
    # Frontmatter without proper --- delimiters
    content = """title: Bad Page
created: 2026-04-14
type: concept

# Not Proper Frontmatter

Just regular text that looks like YAML.
"""
    path = temp_page("concepts", "improper-frontmatter-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Should flag as missing proper frontmatter
    assert "CRITICAL" in output or "WARNING" in output, \
        f"Expected issue for improper frontmatter, got: {output}"


def test_empty_tags_array_allowed(temp_page):
    """
    Create file with empty tags array [].
    Should not report CRITICAL for empty tags.
    """
    content = """---
title: Empty Tags Test
created: 2026-04-14
updated: 2026-04-14
type: concept
tags: []
sources: []
---

# Content
"""
    path = temp_page("concepts", "empty-tags-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Empty tags should not be a CRITICAL issue for THIS file
    lines = output.split("\n")
    critical_lines = [l for l in lines if "CRITICAL" in l and "empty-tags-test" in l]
    assert len(critical_lines) == 0, \
        f"Empty tags should not cause CRITICAL for this file: {critical_lines}"
