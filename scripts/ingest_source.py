#!/usr/bin/env python3
"""Enqueue sources to content_queue.json for LLM-Wiki processing."""

import argparse
import fcntl
import json
import os
import re
import sys
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def compute_quality_score(content: str, title: str = "") -> int:
    """
    Compute a quality score (1-100) for content.
    Uses heuristics: length, structure, uniqueness signals.
    Replace with fabric/LLM scoring by swapping this function body.
    """
    score = 30  # baseline

    # Length signal
    word_count = len(content.split())
    if word_count > 500:
        score += 20
    elif word_count > 200:
        score += 10

    # Structure signal (has headings, lists)
    headings = len(re.findall(r'^#+\s', content, re.MULTILINE))
    lists = len(re.findall(r'^[\*\-\+]\s', content, re.MULTILINE))
    score += min(headings * 3, 15)
    score += min(lists * 1, 15)

    # Title presence
    if title and len(title) > 5:
        score += 10

    # URL richness
    urls = len(re.findall(r'https?://', content))
    score += min(urls * 2, 10)

    # Penalize very short content
    if word_count < 50:
        score = max(score - 20, 1)

    return min(max(score, 1), 100)

# Use environment variable for vault path, default to local development path
VAULT = Path(os.environ.get("WIKI_VAULT", Path.home() / "library"))
QUEUE_FILE = VAULT / "content_queue.json"


def init_queue():
    """Create queue file with empty array if missing."""
    if not os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "w") as f:
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
    path = parsed.path.rstrip("/")
    if path:
        filename = path.split("/")[-1]
        # Remove file extension
        title = re.sub(r"\.[^.]+$", "", filename)
        # Replace underscores with spaces, capitalize
        title = title.replace("-", " ").replace("_", " ")
        if title:
            return title
    # Fallback to domain
    return parsed.netloc


def is_youtube_url(url):
    """Check if URL is a YouTube video."""
    parsed = urlparse(url)
    return "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc


def enqueue(url, influencer=None, doc_type="concept", title=None, content=None, quality_score=None):
    """Add a task to the queue."""
    init_queue()

    task_id = generate_id()
    title = extract_title(url, title)
    is_youtube = is_youtube_url(url)

    # Compute score if content provided and not already set
    if quality_score is None and content:
        quality_score = compute_quality_score(content, title)

    task = {
        "id": task_id,
        "url": url,
        "influencer": influencer,
        "type": doc_type,
        "title": title,
        "status": "Unassigned",
        "quality_score": quality_score,
    }

    if is_youtube:
        task["youtube"] = True

    with open(QUEUE_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        q = json.load(f)
        q.append(task)
        f.seek(0)
        json.dump(q, f, indent=2)
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)

    return task_id


def main():
    parser = argparse.ArgumentParser(description="Enqueue sources to LLM-Wiki queue")
    parser.add_argument("--url", required=True, help="Source URL")
    parser.add_argument("--influencer", help="Influencer name")
    parser.add_argument(
        "--type",
        choices=["concept", "entity", "comparison", "query"],
        default="concept",
        help="Document type",
    )
    parser.add_argument("--title", help="Explicit title (overrides URL-derived)")
    parser.add_argument("--content", help="Raw content text to compute quality score")
    parser.add_argument("--score", type=int, choices=range(1, 101),
                       help="Quality score 1-100 (auto-computed from --content if omitted)")

    args = parser.parse_args()

    # Auto-compute score from content if provided and --score not set
    score = args.score
    if score is None and args.content:
        score = compute_quality_score(args.content, args.title)

    try:
        task_id = enqueue(args.url, args.influencer, args.type, args.title,
                          quality_score=score)
        print(task_id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
