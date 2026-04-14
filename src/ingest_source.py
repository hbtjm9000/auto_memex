#!/usr/bin/env python3
"""Enqueue sources to content_queue.json for LLM-Wiki processing."""

import argparse
import json
import os
import re
import sys
import fcntl
from datetime import datetime
from urllib.parse import urlparse

QUEUE_FILE = '/home/hbtjm/library/content_queue.json'

def init_queue():
    """Create queue file with empty array if missing."""
    if not os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'w') as f:
            json.dump([], f)

def generate_id():
    """Generate 8-character hex ID."""
    return os.urandom(4).hex()

def extract_title(url, provided_title=None):
    """Extract title from URL or use provided title."""
    if provided_title:
        return provided_title
    # Try to derive title from URL path
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    if path:
        filename = path.split('/')[-1]
        # Remove file extension
        title = re.sub(r'\.[^.]+$', '', filename)
        # Replace underscores with spaces, capitalize
        title = title.replace('-', ' ').replace('_', ' ')
        if title:
            return title
    # Fallback to domain
    return parsed.netloc

def is_youtube_url(url):
    """Check if URL is a YouTube video."""
    parsed = urlparse(url)
    return 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc

def enqueue(url, influencer=None, doc_type='concept', title=None):
    """Add a task to the queue."""
    init_queue()
    
    task_id = generate_id()
    title = extract_title(url, title)
    is_youtube = is_youtube_url(url)
    
    task = {
        'id': task_id,
        'url': url,
        'influencer': influencer,
        'type': doc_type,
        'title': title,
        'status': 'Unassigned'
    }
    
    if is_youtube:
        task['youtube'] = True
    
    with open(QUEUE_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        q = json.load(f)
        q.append(task)
        f.seek(0)
        json.dump(q, f, indent=2)
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)
    
    return task_id

def main():
    parser = argparse.ArgumentParser(description='Enqueue sources to LLM-Wiki queue')
    parser.add_argument('--url', required=True, help='Source URL')
    parser.add_argument('--influencer', help='Influencer name')
    parser.add_argument('--type', choices=['concept', 'entity', 'comparison', 'query'],
                        default='concept', help='Document type')
    parser.add_argument('--title', help='Explicit title (overrides URL-derived)')
    
    args = parser.parse_args()
    
    try:
        task_id = enqueue(args.url, args.influencer, args.type, args.title)
        print(task_id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
