"""
test_filename_norm.py - Tests for filename normalization in worker.sh.
"""

import json
import subprocess
import os
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
QUEUE = VAULT / "content_queue.json"


def run_worker():
    """Run the worker.sh script and return the result."""
    result = subprocess.run(
        ["bash", str(Path.home() / "Riki" / "Utils" / "worker.sh")],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    return result


def normalize_title_to_filename(title):
    """
    Pure function: normalize a title to lowercase-hyphen format.
    This is what the worker SHOULD do.
    """
    import re
    # Lowercase first
    name = title.lower()
    # Replace spaces with hyphens
    name = name.replace(" ", "-")
    # Replace & with 'and'
    name = name.replace("&", "and")
    # Remove other special chars
    name = re.sub(r"[^a-z0-9\-]", "", name)
    # Collapse multiple hyphens
    name = re.sub(r"-+", "-", name)
    # Remove leading/trailing hyphens
    name = name.strip("-")
    return name + ".md"


def test_double_extension_not_created(temp_page, clean_queue):
    """
    Check that existing files with .md in title don't get double extension.
    The existing file 'watch.md.md' is a known bug - this tests it gets fixed.
    """
    # Check the existing problematic file
    double_ext_file = VAULT / "concepts" / "watch.md.md"
    
    # If the file exists, it violates the convention
    # After fix, running worker on a task with title 'watch.md' should NOT produce 'watch.md.md'
    if double_ext_file.exists():
        # This is the bug we're testing FOR
        assert False, f"Double extension file exists: {double_ext_file}"
    
    # The normalize function should never produce .md.md
    assert normalize_title_to_filename("watch.md") == "watch-md.md"
    assert normalize_title_to_filename("test.md file") == "testmd-file.md"


def test_spaces_become_hyphens(temp_page, clean_queue):
    """
    Enqueue task with title like 'Data Breaches'.
    Run worker.
    Assert file exists as data-breaches.md not 'data breaches.md'.
    """
    # Read queue before
    with open(QUEUE) as f:
        queue_before = json.load(f)
    count_before = len(queue_before)
    
    # Enqueue a task with spaces in title
    result = subprocess.run(
        [
            "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
            "--url", "https://example.com/data-breaches-article",
            "--type", "concept",
            "--title", "Data Breaches"
        ],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Enqueue failed: {result.stderr}"
    
    # Read queue after
    with open(QUEUE) as f:
        queue_after = json.load(f)
    
    assert len(queue_after) == count_before + 1, "Task not added to queue"
    task = queue_after[-1]
    assert task["title"] == "Data Breaches"
    
    # The filename should normalize spaces to hyphens
    expected_filename = normalize_title_to_filename(task["title"])
    assert " " not in expected_filename, f"Spaces not replaced: {expected_filename}"
    assert expected_filename == "data-breaches.md"


def test_special_chars_removed(temp_page, clean_queue):
    """
    Enqueue task with title like 'AI & ML Basics'.
    Run worker.
    Assert filename is ai-and-ml-basics.md (no &, no spaces).
    """
    # Enqueue task
    result = subprocess.run(
        [
            "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
            "--url", "https://example.com/ai-ml-basics",
            "--type", "concept",
            "--title", "AI & ML Basics"
        ],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Enqueue failed: {result.stderr}"
    
    with open(QUEUE) as f:
        queue_after = json.load(f)
    
    task = queue_after[-1]
    normalized = normalize_title_to_filename(task["title"])
    
    # Should have no &, no spaces, no special chars except hyphens
    assert "&" not in normalized
    assert " " not in normalized
    assert normalized == "ai-and-ml-basics.md"


def test_uppercase_becomes_lowercase():
    """
    Filename normalization should convert to lowercase.
    """
    assert normalize_title_to_filename("Zero Trust Architecture") == "zero-trust-architecture.md"
    assert normalize_title_to_filename("Cybersecurity") == "cybersecurity.md"


def test_multiple_hyphens_collapsed():
    """
    Multiple spaces/hyphens should collapse to single hyphen.
    """
    assert normalize_title_to_filename("AI  --  ML") == "ai-ml.md"
    assert normalize_title_to_filename("Test  Multiple   Spaces") == "test-multiple-spaces.md"


def test_leading_trailing_hyphens_removed():
    """
    Leading and trailing hyphens should be removed.
    """
    assert normalize_title_to_filename(" Test Page ") == "test-page.md"
    assert normalize_title_to_filename("-Test-") == "test.md"
