import json
import sys
import os
import fcntl

QUEUE_FILE = '/home/hbtjm/library/content_queue.json'

def init_queue():
    if not os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'w') as f:
            json.dump([], f)

def pop_task():
    init_queue()
    with open(QUEUE_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        q = json.load(f)
        for task in q:
            if task['status'] == 'Unassigned':
                # Capture original status before changing
                original_status = task['status']
                task['status'] = 'Open'
                f.seek(0)
                json.dump(q, f, indent=2)
                f.truncate()
                fcntl.flock(f, fcntl.LOCK_UN)
                # Return original status so caller knows it was Unassigned
                task['status'] = original_status
                print(json.dumps(task))
                return
        fcntl.flock(f, fcntl.LOCK_UN)
        print(json.dumps({"error": "No Unassigned tasks available"}))

def mark_done(task_id):
    with open(QUEUE_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        q = json.load(f)
        for task in q:
            if task['id'] == task_id:
                task['status'] = 'Done'
                break
        f.seek(0)
        json.dump(q, f, indent=2)
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)
        print(f"Task {task_id} marked Done.")

def get_stats():
    init_queue()
    with open(QUEUE_FILE, 'r') as f:
        q = json.load(f)
        unassigned = sum(1 for t in q if t['status'] == 'Unassigned')
        open_tasks = sum(1 for t in q if t['status'] == 'Open')
        done = sum(1 for t in q if t['status'] == 'Done')
        print(f"Queue Stats -> Unassigned: {unassigned}, Open: {open_tasks}, Done: {done}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python queue_manager.py [pop|complete <id>|stats]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == 'pop':
        pop_task()
    elif cmd == 'complete':
        mark_done(sys.argv[2])
    elif cmd == 'stats':
        get_stats()