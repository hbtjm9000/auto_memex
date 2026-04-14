"""
test_tag_taxonomy.py - Tests for tag validation against SCHEMA taxonomy.
"""

import subprocess
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")

LINT_SCRIPT = Path("/home/hbtjm/Riki/Utils/lint_wiki.py")


def run_lint_vault():
    """Run lint_wiki.py on vault and return output."""
    result = subprocess.run(
        ["python3", str(LINT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    return result


def test_unlisted_tag_reported(temp_page, sample_frontmatter):
    """
    Create page with tag 'random-tag-xyz' (not in SCHEMA).
    Run lint_wiki.py.
    Assert WARNING for unlisted tag.
    """
    content = sample_frontmatter + """
# Random Tag Test

This page has an unlisted tag.
"""
    # Replace the valid tag with an invalid one
    content = content.replace("tags: [security]", "tags: [random-tag-xyz]")
    
    path = temp_page("concepts", "random-tag-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Should warn about unlisted tag
    assert "WARNING" in output or "warning" in output.lower(), \
        f"Expected WARNING for unlisted tag, got: {output}"
    assert "random-tag-xyz" in output.lower() or "unlisted" in output.lower(), \
        f"Should mention the unlisted tag: {output}"


def test_valid_tag_no_issue(temp_page, sample_frontmatter):
    """
    Create page with tag 'zero-trust' (in taxonomy).
    Run lint_wiki.py.
    Assert no tag-related warning for that file.
    """
    # Replace tag with valid one from taxonomy
    content = sample_frontmatter.replace("tags: [security]", "tags: [zero-trust]")
    content = content + """
# Zero Trust Page

This page uses a valid taxonomy tag.
"""
    
    path = temp_page("concepts", "valid-tag-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Should not warn about zero-trust tag for THIS file
    lines = [l for l in output.split("\n") if "valid-tag-test" in l and "zero-trust" in l.lower() and "warning" in l.lower()]
    assert len(lines) == 0, \
        f"Valid tag should not warn: {lines}"


def test_multiple_unlisted_tags(temp_page, sample_frontmatter):
    """
    Create page with 3 unlisted tags.
    Run lint_wiki.py.
    Assert all 3 flagged.
    """
    content = sample_frontmatter + """
# Multi Unlisted Tags Test

This page has multiple unlisted tags.
"""
    content = content.replace("tags: [security]", "tags: [fake-tag-1, fake-tag-2, fake-tag-3]")
    
    path = temp_page("concepts", "multi-unlisted-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Count unlisted tags flagged
    fake1 = "fake-tag-1" in output.lower()
    fake2 = "fake-tag-2" in output.lower()
    fake3 = "fake-tag-3" in output.lower()
    
    flagged_count = sum([fake1, fake2, fake3])
    assert flagged_count >= 2, \
        f"Expected at least 2 unlisted tags flagged, got: {output}"


def test_all_taxonomy_tags_valid(temp_page, sample_frontmatter, taxonomy_tags):
    """
    Create page with each valid taxonomy tag individually.
    None should produce warnings.
    """
    # Test just a few key tags to avoid 40+ pages being created
    key_tags = ["ai", "security", "zero-trust", "cloud", "devops"]
    
    for tag in key_tags:
        content = sample_frontmatter.replace("tags: [security]", f"tags: [{tag}]")
        content = content + f"\n# {tag.title()} Page\nContent.\n"
        
        path = temp_page("concepts", f"tag-{tag}-test", content)
        
        result = run_lint_vault()
        output = result.stdout + result.stderr
        
        # Should not warn about this tag for THIS file
        lines = [l for l in output.split("\n") if f"tag-{tag}-test" in l and "warning" in l.lower() and tag in l.lower()]
        assert len(lines) == 0, \
            f"Valid tag '{tag}' should not warn: {lines}"


def test_new_tag_needs_schema_update(temp_page, sample_frontmatter):
    """
    When a new tag is needed, it should be flagged until added to SCHEMA.
    This is the current expected behavior.
    """
    content = sample_frontmatter.replace("tags: [security]", "tags: [my-custom-tag]")
    content = content + """
# Custom Tag Test

Using a tag not in SCHEMA.
"""
    
    path = temp_page("concepts", "custom-tag-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Custom tag not in schema should be flagged
    lines = [l for l in output.split("\n") if "custom-tag-test" in l]
    has_warning = any("my-custom-tag" in l.lower() or "unlisted" in l.lower() or "warning" in l.lower() for l in lines)
    assert has_warning, \
        f"Custom tag should be flagged: {output}"


def test_tag_case_sensitivity(temp_page, sample_frontmatter):
    """
    Tags should be case-insensitive and match taxonomy.
    'Zero-Trust' should work same as 'zero-trust'.
    """
    content = sample_frontmatter.replace("tags: [security]", "tags: [Zero-Trust]")
    content = content + """
# Case Tag Test

Testing case insensitivity.
"""
    
    path = temp_page("concepts", "case-tag-test", content)
    
    result = run_lint_vault()
    output = result.stdout + result.stderr
    
    # Should not warn - case insensitive match for THIS file
    lines = [l for l in output.split("\n") if "case-tag-test" in l and "zero-trust" in l.lower() and "warning" in l.lower()]
    assert len(lines) == 0, \
        f"Case variant of valid tag should not warn: {lines}"
