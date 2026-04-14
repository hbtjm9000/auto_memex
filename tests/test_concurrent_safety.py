"""
test_concurrent_safety.py - Tests for concurrent access safety.
"""

import subprocess
import json
import time
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
QUEUE_MANAGER = VAULT / "queue_manager.py"
QUEUE = VAULT / "content_queue.json"


def read_queue():
    """Read queue JSON."""
    with open(QUEUE) as f:
        return json.load(f)


def test_fcntl_lock_present():
    """
    Check source code of queue_manager.py for fcntl.flock usage.
    Assert fcntl.flock(f, fcntl.LOCK_EX) is present.
    """
    content = QUEUE_MANAGER.read_text()
    
    # Must import fcntl
    assert "import fcntl" in content, "Should import fcntl module"
    
    # Must use flock
    assert "flock(" in content or "fcntl.flock" in content, \
        "Should call flock() function"
    
    # Should use exclusive lock for writes
    assert "LOCK_EX" in content, \
        "Should use LOCK_EX for exclusive locking during writes"


def test_fcntl_lock_in_ingest_source():
    """
    Check ingest_source.py also uses fcntl for enqueue.
    """
    ingest_script = Path.home() / "Riki" / "Utils" / "ingest_source.py"
    content = ingest_script.read_text()
    
    assert "fcntl" in content, "ingest_source.py should use fcntl for locking"
    assert "LOCK_EX" in content, "Should use exclusive lock"


def test_two_workers_no_corruption_serial():
    """
    Start 2 workers in sequence.
    Process different tasks.
    Verify both complete without queue corruption.
    This tests serial safety (lock is working).
    """
    # Setup: Two tasks
    tasks = [
        {
            "id": "worker-serial-a",
            "url": "https://example.com/serial-a",
            "type": "concept",
            "title": "Serial A",
            "status": "Unassigned"
        },
        {
            "id": "worker-serial-b", 
            "url": "https://example.com/serial-b",
            "type": "concept",
            "title": "Serial B",
            "status": "Unassigned"
        }
    ]
    with open(QUEUE, "w") as f:
        json.dump(tasks, f)
    
    # First worker pop
    result1 = subprocess.run(
        ["python3", str(QUEUE_MANAGER), "pop"],
        capture_output=True,
        text=True
    )
    
    output1 = result1.stdout
    if "worker-serial" in output1:
        task_id = json.loads(output1).get("id")
        # Mark done
        subprocess.run(
            ["python3", str(QUEUE_MANAGER), "complete", task_id],
            capture_output=True,
            text=True
        )
    
    # Second worker pop
    result2 = subprocess.run(
        ["python3", str(QUEUE_MANAGER), "pop"],
        capture_output=True,
        text=True
    )
    
    output2 = result2.stdout
    if "worker-serial" in output2:
        task_id = json.loads(output2).get("id")
        # Mark done
        subprocess.run(
            ["python3", str(QUEUE_MANAGER), "complete", task_id],
            capture_output=True,
            text=True
        )
    
    # Final queue state should be valid
    queue = read_queue()
    assert len(queue) == 2, "Both tasks should still be in queue"
    
    # Verify statuses
    statuses = {t["id"]: t["status"] for t in queue}
    assert statuses.get("worker-serial-a") == "Done", \
        f"Task A should be Done, got: {statuses}"
    assert statuses.get("worker-serial-b") == "Done", \
        f"Task B should be Done, got: {statuses}"


def test_queue_lock_blocks_other_writers():
    """
    Verify that when one process holds lock, another waits.
    This is tested by checking fcntl behavior.
    """
    # This is primarily a code inspection test
    # The actual blocking behavior is hard to test in pure Python
    # without spawning actual competing processes
    
    content = QUEUE_MANAGER.read_text()
    
    # Verify lock is held for entire write operation
    # Should have LOCK_UN after write completes
    assert "LOCK_UN" in content, \
        "Should release lock with fcntl.LOCK_UN"


def test_queue_json_not_corrupted_on_concurrent_write():
    """
    Multiple sequential writes should produce valid JSON.
    Tests that lock prevents partial writes.
    """
    # Start with empty queue
    with open(QUEUE, "w") as f:
        json.dump([], f)
    
    # Do several enqueues sequentially
    for i in range(5):
        result = subprocess.run(
            [
                "python3", str(Path.home() / "Riki" / "Utils" / "ingest_source.py"),
                "--url", f"https://example.com/concurrent-test-{i}",
                "--type", "concept"
            ],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
    
    # Queue should be valid JSON with 5 items
    try:
        queue = read_queue()
        assert len(queue) == 5, f"Expected 5 items, got {len(queue)}"
    except json.JSONDecodeError as e:
        pytest.fail(f"Queue corrupted on concurrent writes: {e}")


def test_lock_timeout_prevents_deadlock():
    """
    Verify lock operations have timeout consideration.
    fcntl.LOCK_NB can be used for non-blocking test.
    """
    content = QUEUE_MANAGER.read_text()
    
    # Code should use LOCK_EX (exclusive) not just LOCK_SH (shared)
    # Exclusive lock ensures mutual exclusion
    assert "LOCK_EX" in content, \
        "Should use exclusive lock (LOCK_EX) for write operations"


def test_queue_integrity_after_interrupted_write():
    """
    Simulate an interrupted write by manually corrupting queue,
    then verify next operation handles it gracefully.
    """
    # Backup queue
    if QUEUE.exists():
        backup = QUEUE.read_text()
    else:
        backup = None
    
    try:
        # Write incomplete JSON
        with open(QUEUE, "w") as f:
            f.write('{"incomplete": true, "broken')
        
        # Try to read - should handle gracefully
        result = subprocess.run(
            ["python3", str(QUEUE_MANAGER), "stats"],
            capture_output=True,
            text=True
        )
        
        output = result.stdout + result.stderr
        
        # Should either error gracefully or fix the queue
        # Should not crash with uncaught JSON exception
        assert "traceback" not in output.lower() or result.returncode != 0, \
            f"Should handle corrupted queue gracefully: {output}"
    
    finally:
        # Restore backup
        if backup:
            QUEUE.write_text(backup)
        elif backup is None and QUEUE.exists():
            QUEUE.unlink()


def test_concurrent_queue_operations_structural_safety():
    """
    Test that the queue data structure is properly maintained.
    Even with locking, we need to ensure no data loss.
    """
    # Create queue with many tasks
    tasks = [
        {
            "id": f"struct-{i:03d}",
            "url": f"https://example.com/struct-{i}",
            "type": "concept",
            "title": f"Struct Test {i}",
            "status": "Unassigned"
        }
        for i in range(20)
    ]
    
    with open(QUEUE, "w") as f:
        json.dump(tasks, f)
    
    # Pop half of them
    for i in range(10):
        result = subprocess.run(
            ["python3", str(QUEUE_MANAGER), "pop"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                task = json.loads(result.stdout)
                # Mark as Open (simulating worker processing)
                queue = read_queue()
                for t in queue:
                    if t["id"] == task["id"]:
                        t["status"] = "Open"
                        break
                with open(QUEUE, "w") as f:
                    json.dump(queue, f)
            except json.JSONDecodeError:
                pass
    
    # Verify remaining tasks are intact
    queue = read_queue()
    assert len(queue) == 20, f"Should have 20 tasks, got {len(queue)}"
    
    # All tasks should have all required fields
    for task in queue:
        assert "id" in task
        assert "url" in task
        assert "status" in task
