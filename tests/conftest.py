"""
conftest.py - Shared pytest fixtures for LLM-Wiki V2 test suite.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
QUEUE = VAULT / "content_queue.json"
INDEX = VAULT / "index.md"
LOG = VAULT / "log.md"


@pytest.fixture
def VAULT_PATH():
    """Return the vault path."""
    return VAULT


@pytest.fixture
def temp_page():
    """
    Fixture to create and automatically clean up a temp wiki page.
    
    Usage:
        def test_something(temp_page):
            path = temp_page("concepts", "test-page", "# Test content")
            # ... test code runs ...
            # ... automatic cleanup happens after test ...
    
    Args:
        subdir: Subdirectory under vault (e.g., "concepts", "entities")
        filename: Filename without extension (extension .md is added)
        content: Full file content including frontmatter
    
    Yields:
        Path to the created temp file
    """
    created_files = []
    
    def _create_page(subdir: str, filename: str, content: str) -> Path:
        subdir_path = VAULT / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        file_path = subdir_path / f"{filename}.md"
        file_path.write_text(content)
        created_files.append(file_path)
        return file_path
    
    yield _create_page
    
    # Cleanup after test
    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()


@pytest.fixture
def clean_queue():
    """
    Fixture to save and restore queue state around a test.
    
    Usage:
        def test_something(clean_queue):
            # ... test runs with queue restored after ...
    
    Yields:
        None
    """
    # Save queue state before test
    queue_backup = None
    if QUEUE.exists():
        queue_backup = QUEUE.read_text()
    
    yield
    
    # Restore queue state after test
    if queue_backup is not None:
        QUEUE.write_text(queue_backup)
    elif QUEUE.exists():
        QUEUE.unlink()


@pytest.fixture
def clean_index():
    """
    Fixture to save and restore index.md around a test.
    
    Yields:
        None
    """
    index_backup = None
    if INDEX.exists():
        index_backup = INDEX.read_text()
    
    yield
    
    if index_backup is not None:
        INDEX.write_text(index_backup)
    elif INDEX.exists():
        INDEX.unlink()


@pytest.fixture
def sample_frontmatter():
    """Return a minimal valid frontmatter block."""
    return """---
title: Test Page
created: 2026-04-14
updated: 2026-04-14
type: concept
tags: [security]
sources: []
---

"""


@pytest.fixture
def taxonomy_tags():
    """Return the set of valid tags from SCHEMA.md."""
    return {
        "ai", "ml", "cloud", "security", "devops", "networking",
        "virtualization", "msp", "mssp", "saas", "consulting",
        "managed-services", "pricing", "sla", "zero-trust", "iam",
        "edr", "sip", "vulnerability", "compliance", "incident-response",
        "ci/cd", "microservices", "api", "containerization", "iac",
        "monitoring", "backup", "dr", "rmm", "psa", "ticketing",
        "automation", "comparison", "timeline", "trend", "prediction",
        "vendor-review"
    }
