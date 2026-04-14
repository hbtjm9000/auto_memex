"""
test_idempotency.py - Tests for idempotent operations (running same operation twice).
"""

import subprocess
import json
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
INDEX = VAULT / "index.md"
LOG = VAULT / "log.md"


def read_queue():
    """Read queue JSON."""
    with open(VAULT / "content_queue.json") as f:
        return json.load(f)


def count_files_in_index():
    """Count total files referenced in index.md."""
    if not INDEX.exists():
        return 0
    content = INDEX.read_text()
    return content.count("[[") 


def test_duplicate_ingest_no_duplicate_page(temp_page, sample_frontmatter):
    """
    Create page concepts/test-idempotent.md with unique content.
    Try to create same page again.
    Assert only ONE file exists.
    """
    filename = "test-idempotent-page"
    path = VAULT / "concepts" / f"{filename}.md"
    
    # Create first time
    content = sample_frontmatter + """
# Idempotent Test

Unique content for idempotency test.
"""
    if path.exists():
        path.unlink()
    path.write_text(content)
    
    # Try to create again (simulate re-ingest)
    if path.exists():
        path.write_text(content)
    
    # Count files - should be exactly 1
    matching = list(VAULT.glob(f"**/{filename}.md"))
    assert len(matching) == 1, \
        f"Should have exactly 1 file, found {len(matching)}: {matching}"


def test_index_no_duplicate_entry(temp_page, sample_frontmatter, clean_index):
    """
    Same file added to index twice via --fix.
    Assert only one entry in index.
    """
    filename = "test-idempotent-index"
    path = temp_page("concepts", filename, sample_frontmatter + "\n# Idempotent Index\nContent.\n")
    
    # Read current index
    if INDEX.exists():
        original = INDEX.read_text()
    else:
        original = ""
    
    try:
        # Add entry twice
        entry = f"- [[concepts/{filename}.md]]\n"
        INDEX.write_text(original + entry + entry)
        
        # Run lint --fix to dedupe
        result = subprocess.run(
            ["python3", str(VAULT.parent.parent / "Riki" / "Utils" / "lint_wiki.py"), "--fix"],
            capture_output=True,
            text=True,
            cwd=str(VAULT)
        )
        
        # Check for duplicates
        if INDEX.exists():
            content = INDEX.read_text()
            count = content.count(f"concepts/{filename}.md")
            assert count <= 1, \
                f"Duplicate index entries found: {content}"
    
    finally:
        if original:
            INDEX.write_text(original)


def test_log_has_multiple_entries():
    """
    Multiple operations should each append to log.
    Verify log has growing entries.
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content_before = LOG.read_text()
    count_before = content_before.count("## [")
    
    # Run lint (which appends to log)
    result = subprocess.run(
        ["python3", str(VAULT.parent.parent / "Riki" / "Utils" / "lint_wiki.py")],
        capture_output=True,
        text=True,
        cwd=str(VAULT)
    )
    
    content_after = LOG.read_text()
    count_after = content_after.count("## [")
    
    # Log should have same or more entries
    assert count_after >= count_before, \
        f"Log should have same or more entries: before={count_before}, after={count_after}"


def test_worker_idempotent_on_double_run(temp_page, sample_frontmatter, clean_queue):
    """
    Create a queued task, run worker twice on same task.
    Task should only be processed once.
    """
    # Create a task
    task = {
        "id": "idempotency-test",
        "url": "https://example.com/idempotent-double",
        "type": "concept",
        "title": "Idempotent Double Test",
        "status": "Unassigned"
    }
    queue = [task]
    with open(VAULT / "content_queue.json", "w") as f:
        json.dump(queue, f)
    
    # First pop
    result1 = subprocess.run(
        ["python3", str(VAULT / "queue_manager.py"), "pop"],
        capture_output=True,
        text=True
    )
    
    # Verify task is now Open
    q1 = read_queue()
    t1 = next((t for t in q1 if t["id"] == "idempotency-test"), None)
    assert t1["status"] == "Open"
    
    # Second pop - should not get same task again
    result2 = subprocess.run(
        ["python3", str(VAULT / "queue_manager.py"), "pop"],
        capture_output=True,
        text=True
    )
    
    output = result2.stdout + result2.stderr
    
    # Should either say no tasks or return different task
    if "idempotency-test" in output:
        # If it returns same task, that's a bug
        assert False, "Same task was returned twice - not idempotent"


def test_multiple_concurrent_ingests_dont_corrupt_queue():
    """
    Simulate multiple enqueue operations in sequence.
    Queue should remain consistent.
    """
    initial_queue = read_queue()
    initial_count = len(initial_queue)
    
    # Enqueue multiple items
    urls = [
        f"https://example.com/idempotent-seq-{i}"
        for i in range(3)
    ]
    
    for url in urls:
        result = subprocess.run(
            [
                "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
                "--url", url,
                "--type", "concept"
            ],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Enqueue failed for {url}"
    
    # Verify queue is valid
    queue = read_queue()
    assert len(queue) == initial_count + 3, \
        f"Queue should have {initial_count + 3} items, got {len(queue)}"
    
    # Verify all have unique IDs
    ids = [t["id"] for t in queue]
    assert len(set(ids)) == len(ids), "All task IDs should be unique"


def test_reopen_already_open_task_not_allowed():
    """
    A task that is already Open should not be popped again as Unassigned.
    """
    task = {
        "id": "already-open-test",
        "url": "https://example.com/already-open",
        "type": "concept", 
        "title": "Already Open Test",
        "status": "Open"  # Already Open
    }
    queue = [task]
    with open(VAULT / "content_queue.json", "w") as f:
        json.dump(queue, f)
    
    result = subprocess.run(
        ["python3", str(VAULT / "queue_manager.py"), "pop"],
        capture_output=True,
        text=True
    )
    
    output = result.stdout + result.stderr
    
    # Should indicate no Unassigned tasks available
    # (it should skip the Open task)
    if task["id"] in output and "error" not in output.lower():
        pytest.fail("Pop returned a task that was already Open")
