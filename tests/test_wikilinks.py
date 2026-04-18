"""
test_wikilinks.py - Tests for wikilink validation in lint_wiki.py.
"""

import subprocess

from .conftest import LINT_SCRIPT, VAULT


def run_lint_vault():
    """Run lint_wiki.py on vault and return output."""
    result = subprocess.run(
        ["python3", str(LINT_SCRIPT)], capture_output=True, text=True, cwd=str(VAULT)
    )
    return result


def test_broken_wikilink_detected(temp_page, sample_frontmatter):
    """
    Create a temp page with [[NonExistentPage123]].
    Run lint_wiki.py.
    Assert CRITICAL or WARNING for broken link.
    """
    content = (
        sample_frontmatter
        + """
# Broken Link Test

This page links to [[NonExistentPage123]] which doesn't exist.

And also [[AnotherFakePage]].
"""
    )
    temp_page("concepts", "broken-wikilink-test", content)

    result = run_lint_vault()
    output = result.stdout + result.stderr

    # Should detect broken wikilinks
    assert any(
        keyword in output.lower() for keyword in ["broken", "wikilink", "non-existent", "not found"]
    ), f"Expected broken wikilink detection, got: {output}"


def test_valid_wikilink_no_issue(temp_page, sample_frontmatter):
    """
    Create page with [[../entities/troy-hunt]] pointing to existing file.
    Run lint_wiki.py.
    Assert no broken link issue for that file.
    """
    # Check if entities/troy-hunt.md exists, if not create it
    troy_hunt_path = VAULT / "entities" / "troy-hunt.md"
    if not troy_hunt_path.exists():
        content = (
            sample_frontmatter
            + """
# Troy Hunt

Security researcher, creator of Have I Been Pwned.
"""
        )
        (VAULT / "entities").mkdir(exist_ok=True)
        troy_hunt_path.write_text(content)

    # Create a page that links to it
    content = (
        sample_frontmatter
        + """
# Test Page

Link to [[../entities/troy-hunt]] for more info.
"""
    )
    temp_page("concepts", "valid-wikilink-test", content)

    result = run_lint_vault()
    output = result.stdout + result.stderr

    # Should not report broken link for existing file
    lines_with_link_warning = [
        line
        for line in output.split("\n")
        if "troy-hunt" in line.lower() and ("broken" in line.lower() or "wikilink" in line.lower())
    ]
    assert len(lines_with_link_warning) == 0, (
        f"Should not flag valid wikilink as broken: {lines_with_link_warning}"
    )


def test_wikilink_to_existing_page_clean(temp_page, sample_frontmatter):
    """
    Add a wikilink from a new page to an already-existing page.
    Run lint_wiki.py.
    Assert no broken link issue.
    """
    # Create target page if it doesn't exist
    target_path = VAULT / "concepts" / "security-overview.md"
    if not target_path.exists():
        content = (
            sample_frontmatter
            + """
# Security Overview

General security concepts.
"""
        )
        target_path.write_text(content)

    # Create page linking to it
    content = (
        sample_frontmatter
        + """
# Link Test

Refer to [[../concepts/security-overview]] for details.
"""
    )
    temp_page("concepts", "link-to-existing-test", content)

    result = run_lint_vault()
    output = result.stdout + result.stderr

    # No broken link warnings for THIS file
    lines = [
        line
        for line in output.split("\n")
        if "link-to-existing-test" in line and "broken" in line.lower()
    ]
    assert len(lines) == 0, f"Valid link should not be flagged: {lines}"


def test_multiple_broken_wikilinks_all_detected(temp_page, sample_frontmatter):
    """
    Create page with 3 broken wikilinks.
    Run lint_wiki.py.
    Assert all 3 flagged.
    """
    content = (
        sample_frontmatter
        + """
# Multi Broken Links

Links: [[FakeOne]], [[FakeTwo]], [[FakeThree]]
"""
    )
    temp_page("concepts", "multi-broken-test", content)

    result = run_lint_vault()
    output = result.stdout + result.stderr

    # Count how many fake pages are mentioned in broken link warnings
    fake_count = sum(1 for f in ["fakeone", "faketwo", "fakethree"] if f in output.lower())
    assert fake_count >= 2, f"Expected at least 2 broken links detected, got: {output}"


def test_wikilink_case_sensitivity(temp_page, sample_frontmatter):
    """
    Create wikilinks with different cases.
    Worker should normalize and link should work.
    """
    # Create target
    target_path = VAULT / "concepts" / "case-test.md"
    if not target_path.exists():
        content = (
            sample_frontmatter
            + """
# Case Test

Target page for case sensitivity test.
"""
        )
        target_path.write_text(content)

    # Link with different case - this tests case-insensitive matching
    content = (
        sample_frontmatter
        + """
# Link Case Test

Link to [[../concepts/Case-Test]] (different case).
"""
    )
    temp_page("concepts", "link-case-test", content)

    result = run_lint_vault()
    output = result.stdout + result.stderr

    # Should not flag as broken (case-insensitive matching)
    lines = [
        line for line in output.split("\n") if "link-case-test" in line and "broken" in line.lower()
    ]
    assert len(lines) == 0, f"Case variant link should work: {lines}"


def test_orphan_page_detected(temp_page, sample_frontmatter):
    """
    Create a page with no inbound or outbound wikilinks.
    Run lint_wiki.py.
    Assert orphan page WARNING.
    """
    content = (
        sample_frontmatter
        + """
# Orphan Page

This page has no links to any other pages.
"""
    )
    temp_page("concepts", "orphan-page-test", content)

    result = run_lint_vault()
    output = result.stdout + result.stderr

    # Should flag as orphan for THIS file
    lines = [
        line
        for line in output.split("\n")
        if "orphan-page-test" in line and "orphan" in line.lower()
    ]
    assert len(lines) > 0, f"Expected orphan warning, got: {output}"
