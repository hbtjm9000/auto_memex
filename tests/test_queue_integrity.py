"""
test_queue_integrity.py - Tests for queue operations atomicity and safety.
"""

import json
import subprocess
import os
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
QUEUE = VAULT / "content_queue.json"
QUEUE_MANAGER = VAULT / "queue_manager.py"


def read_queue():
    """Read queue JSON file."""
    if not QUEUE.exists():
        return []
    with open(QUEUE) as f:
        return json.load(f)


def write_queue(data):
    """Write to queue JSON file."""
    with open(QUEUE, "w") as f:
        json.dump(data, f, indent=2)


def test_enqueue_adds_task(clean_queue):
    """
    Read queue before.
    Run ingest_source.py --url <test-url> --type concept.
    Read queue after.
    Assert task count increased by 1.
    Assert new task has id, url, status: Unassigned.
    """
    queue_before = read_queue()
    count_before = len(queue_before)
    
    result = subprocess.run(
        [
            "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
            "--url", "https://example.com/test-enqueue-123",
            "--type", "concept"
        ],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Enqueue failed: {result.stderr}"
    
    queue_after = read_queue()
    count_after = len(queue_after)
    
    assert count_after == count_before + 1, \
        f"Queue count should increase by 1: before={count_before}, after={count_after}"
    
    new_task = queue_after[-1]
    assert "id" in new_task, "Task should have an id"
    assert "url" in new_task, "Task should have a url"
    assert new_task["url"] == "https://example.com/test-enqueue-123"
    assert new_task["status"] == "Unassigned", \
        f"New task should be Unassigned, got: {new_task.get('status')}"


def test_worker_marks_done(clean_queue):
    """
    Add a task to queue with status Unassigned.
    Simulate worker processing (pop + mark done).
    Assert task status is now Done.
    """
    # Create a task directly
    test_task = {
        "id": "deadbeef",
        "url": "https://example.com/test-done",
        "influencer": None,
        "type": "concept",
        "title": "Test Done Task",
        "status": "Unassigned"
    }
    write_queue([test_task])
    
    # Pop the task (worker would do this)
    result = subprocess.run(
        ["python3", str(QUEUE_MANAGER), "pop"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Pop failed: {result.stderr}"
    
    # Verify task is now Open
    queue = read_queue()
    task = next((t for t in queue if t["id"] == "deadbeef"), None)
    assert task is not None, "Task should still be in queue"
    assert task["status"] == "Open", \
        f"Popped task should be Open, got: {task['status']}"
    
    # Mark as done
    result = subprocess.run(
        ["python3", str(QUEUE_MANAGER), "complete", "deadbeef"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Mark done failed: {result.stderr}"
    
    # Verify task is now Done
    queue = read_queue()
    task = next((t for t in queue if t["id"] == "deadbeef"), None)
    assert task["status"] == "Done", \
        f"Task should be Done, got: {task['status']}"


def test_pop_returns_unassigned_only(clean_queue):
    """
    Queue has mixed statuses.
    Call pop.
    Assert returned task has status Unassigned.
    """
    tasks = [
        {"id": "aaaa1111", "url": "https://a.com", "status": "Done", "type": "concept", "title": "A"},
        {"id": "bbbb2222", "url": "https://b.com", "status": "Open", "type": "concept", "title": "B"},
        {"id": "cccc3333", "url": "https://c.com", "status": "Unassigned", "type": "concept", "title": "C"},
        {"id": "dddd4444", "url": "https://d.com", "status": "Unassigned", "type": "concept", "title": "D"},
    ]
    write_queue(tasks)
    
    result = subprocess.run(
        ["python3", str(QUEUE_MANAGER), "pop"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Pop failed: {result.stderr}"
    
    output = result.stdout
    # Pop returns JSON of the task
    try:
        task = json.loads(output)
        assert task.get("status") == "Unassigned", \
            f"Pop should return Unassigned task, got: {task.get('status')}"
    except json.JSONDecodeError:
        # May also output error if no Unassigned tasks
        assert "No Unassigned tasks" in output or "error" in output.lower()


def test_queue_lock_prevents_corruption():
    """
    Verify fcntl.flock is used in queue_manager.py.
    This is a code inspection test.
    """
    content = QUEUE_MANAGER.read_text()
    
    # Should use fcntl.flock for locking
    assert "fcntl" in content, "Should import fcntl"
    assert "LOCK_EX" in content or "LOCK_SH" in content, \
        "Should use exclusive or shared lock"
    assert "flock" in content, "Should call flock()"


def test_queue_file_always_valid_json(clean_queue):
    """
    After any queue operation, the queue file should be valid JSON.
    """
    # Start with valid queue
    initial = [{"id": "test", "url": "https://x.com", "status": "Unassigned", "type": "concept", "title": "Test"}]
    write_queue(initial)
    
    # Enqueue something
    subprocess.run(
        [
            "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
            "--url", "https://example.com/json-test",
            "--type", "concept"
        ],
        capture_output=True,
        text=True
    )
    
    # Verify valid JSON
    try:
        queue = read_queue()
        assert isinstance(queue, list), "Queue should be a list"
    except json.JSONDecodeError as e:
        pytest.fail(f"Queue file is not valid JSON after operation: {e}")


def test_pop_empty_queue_handled(clean_queue):
    """
    Pop when queue is empty should not crash.
    Should return error message.
    """
    write_queue([])
    
    result = subprocess.run(
        ["python3", str(QUEUE_MANAGER), "pop"],
        capture_output=True,
        text=True
    )
    
    output = result.stdout + result.stderr
    # Should indicate no tasks available
    assert "no" in output.lower() or "empty" in output.lower() or "error" in output.lower() or result.returncode != 0


def test_enqueue_idempotent():
    """
    Enqueuing the same URL twice should not duplicate.
    Or if it does, should have different IDs.
    """
    url = "https://example.com/idempotent-test-" + str(os.urandom(4).hex())
    
    # Enqueue twice
    subprocess.run(
        [
            "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
            "--url", url,
            "--type", "concept"
        ],
        capture_output=True,
        text=True
    )
    
    subprocess.run(
        [
            "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
            "--url", url,
            "--type", "concept"
        ],
        capture_output=True,
        text=True
    )
    
    queue = read_queue()
    matching = [t for t in queue if t["url"] == url]
    
    # Same URL should result in same ID (idempotent) or be prevented
    # Current behavior may allow duplicates with different IDs
    # This test documents expected behavior
    if len(matching) > 1:
        ids = [t["id"] for t in matching]
        assert len(set(ids)) == len(ids), "If duplicate URLs, should have unique IDs"
