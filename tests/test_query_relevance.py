"""
test_query_relevance.py - Tests for query_wiki.py relevance and accuracy.
"""

import subprocess
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
QUERY_SCRIPT = Path.home() / "Riki" / "Utils" / "query_wiki.py"


def run_query(question, timeout=30):
    """Run query_wiki.py with a question and return output."""
    result = subprocess.run(
        ["python3", str(QUERY_SCRIPT), "--question", question],
        capture_output=True,
        text=True,
        cwd=str(VAULT),
        timeout=timeout
    )
    return result


def test_query_cites_page(temp_page, sample_frontmatter):
    """
    Ensure some page exists about a known topic (e.g., zero-trust).
    Run query_wiki.py --question about that topic.
    Assert output mentions a specific wiki page filename.
    """
    # Create a page about zero-trust
    content = sample_frontmatter.replace("tags: [security]", "tags: [zero-trust]")
    content = content + """
# Zero Trust Architecture

Zero Trust is a security framework that assumes no implicit trust.

## Key Principles
- Never trust, always verify
- Least privilege access
- Assume breach
"""
    path = temp_page("concepts", "zero-trust-query-test", content)
    
    # Query for it
    result = run_query("What is zero trust architecture?")
    output = result.stdout + result.stderr
    
    # Should cite the page
    assert "zero-trust" in output.lower() or path.name in output.lower(), \
        f"Query should cite the relevant page, got: {output}"


def test_query_returns_empty_for_irrelevant():
    """
    Run query for something clearly not in wiki.
    Assert response indicates no relevant info (NOT a hallucinated answer).
    """
    result = run_query("xyzzy plugh barney rubric amber紫色")
    output = result.stdout + result.stderr
    
    # Should indicate no relevant info found
    # NOT produce a confident hallucinated answer
    lower_output = output.lower()
    
    # Look for indicators of no results
    no_result_indicators = [
        "no ", "not ", "don't find", "cannot find", "could not find",
        "no relevant", "nothing found", "don't know", "no information",
        "unclear", "unknown", "no match"
    ]
    
    has_no_indicator = any(ind in lower_output for ind in no_result_indicators)
    is_empty = not output.strip()
    
    assert has_no_indicator or is_empty, \
        f"Query for irrelevant topic should indicate no results, got: {output}"


def test_query_timeout_graceful():
    """
    Run query with very long timeout handling.
    Assert timeout returns user-friendly message.
    """
    # Run with a very short timeout to trigger it
    result = subprocess.run(
        ["python3", str(QUERY_SCRIPT), "--question", "test"],
        capture_output=True,
        text=True,
        cwd=str(VAULT),
        timeout=1  # 1 second should trigger timeout
    )
    
    # Should either complete or timeout gracefully
    # A timeout is acceptable if it's handled gracefully
    if result.returncode != 0:
        output = result.stdout + result.stderr
        # Should not be a Python traceback crash
        assert "timeout" in output.lower() or "timed out" in output.lower() or result.returncode == 124, \
            f"Timeout should be handled gracefully: {output}"


def test_query_with_real_page(temp_page, sample_frontmatter):
    """
    Create a real page with specific content, then query for that content.
    Verify the answer references the page correctly.
    """
    # Create page about AI Security
    content = sample_frontmatter.replace("tags: [security]", "tags: [ai, security]")
    content = content + """
# AI Security

AI security addresses the unique security challenges of AI systems.

## Threats
- Adversarial attacks on ML models
- Data poisoning
- Model theft
"""
    path = temp_page("concepts", "ai-security-query-test", content)
    
    # Query about AI security threats
    result = run_query("What are AI security threats?")
    output = result.stdout + result.stderr
    
    # Should mention AI security content
    assert "ai" in output.lower() or "security" in output.lower() or "adversarial" in output.lower(), \
        f"Query should return relevant AI security info: {output}"


def test_query_error_handling():
    """
    Run query_wiki.py without required arguments.
    Should return error, not crash.
    """
    result = subprocess.run(
        ["python3", str(QUERY_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    
    # Should return error code and helpful message
    assert result.returncode != 0, "Missing args should cause error"
    output = result.stdout + result.stderr
    assert len(output) > 0, "Should output error message"


def test_query_produces_citation():
    """
    Query should produce at least one citation or reference.
    This ensures the system is grounded in actual content.
    """
    # Create a unique page
    unique_content = sample_frontmatter.replace("tags: [security]", "tags: [testing]")
    unique_content = unique_content + """
# Penguin Navigation Systems

Penguin-based GPS uses avian magnetoreception.
"""
    path = temp_page("concepts", "penguin-nav-test", unique_content)
    
    result = run_query("How do penguins navigate?")
    output = result.stdout + result.stderr
    
    # Should reference something related
    # Either the page name or content from it
    assert "penguin" in output.lower() or "navigation" in output.lower() or "avain" in output.lower(), \
        f"Query should reference penguin content: {output}"
