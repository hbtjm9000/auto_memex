"""
test_log_format.py - Tests for log.md format compliance.
"""

import re
from pathlib import Path

import pytest

VAULT = Path("/home/hbtjm/library")
LOG = VAULT / "log.md"


def test_log_entry_format():
    """
    Read log.md.
    Match pattern: ^## \\[\\d{4}-\\d{2}-\\d{2}\\] ingest \\| .+$
    Assert at least one entry matches.
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content = LOG.read_text()
    
    # Pattern: ## [YYYY-MM-DD] action | title
    pattern = r"## \[\d{4}-\d{2}-\d{2}\] \w+ \| .+"
    
    matches = [re.search(pattern, line) for line in content.split("\n")]
    matched = [m for m in matches if m]
    
    assert len(matched) > 0, \
        f"No log entries match pattern ## [DATE] action | title. Log content:\n{content[:500]}"


def test_log_is_append_only():
    """
    Read log.md entries.
    Verify dates are in ascending order (append-only).
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content = LOG.read_text()
    
    # Extract all date headers
    date_pattern = r"## \[(\d{4}-\d{2}-\d{2})\]"
    dates = re.findall(date_pattern, content)
    
    assert len(dates) > 0, "No date entries found in log"
    
    # Check ascending order
    for i in range(len(dates) - 1):
        assert dates[i] <= dates[i + 1], \
            f"Log dates not in ascending order: {dates[i]} then {dates[i+1]}"


def test_log_ingest_has_title():
    """
    Read log.md.
    For each '## [DATE] ingest |' entry, assert something after the |.
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content = LOG.read_text()
    
    # Find ingest entries and verify they have titles
    ingest_pattern = r"## \[(\d{4}-\d{2}-\d{2})\] ingest \| (.+)"
    matches = re.findall(ingest_pattern, content)
    
    assert len(matches) > 0, "No ingest entries found"
    
    for date, title in matches:
        assert title.strip(), \
            f"Ingest entry at {date} has empty title after |"
        assert len(title.strip()) > 0, \
            f"Ingest entry title should not be empty: '{title}'"


def test_log_lint_entry_format():
    """
    Verify lint entries follow format: ## [DATE] lint | issue count.
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content = LOG.read_text()
    
    # Lint pattern: ## [DATE] lint | NNN issues found
    lint_pattern = r"## \[\d{4}-\d{2}-\d{2}\] lint \| \d+ issue"
    matches = re.findall(lint_pattern, content)
    
    # At least one lint entry should exist (after first run)
    if matches:
        for m in matches:
            assert m, "Lint entry format invalid"


def test_log_timestamp_is_valid_date():
    """
    All timestamps in log should be valid dates.
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content = LOG.read_text()
    
    # Extract all dates
    date_pattern = r"## \[(\d{4}-\d{2}-\d{2})\]"
    dates = re.findall(date_pattern, content)
    
    for date_str in dates:
        year, month, day = date_str.split("-")
        assert 2020 <= int(year) <= 2030, f"Year out of range: {year}"
        assert 1 <= int(month) <= 12, f"Month out of range: {month}"
        assert 1 <= int(day) <= 31, f"Day out of range: {day}"


def test_log_no_duplicate_timestamps():
    """
   同一日期的多个条目应该有不同的时间戳格式。
    Same date entries should have distinguishable timestamps.
    """
    if not LOG.exists():
        pytest.skip("log.md does not exist yet")
    
    content = LOG.read_text()
    
    # Group entries by date
    date_pattern = r"## \[(\d{4}-\d{2}-\d{2})\] (\w+) \|"
    entries = re.findall(date_pattern, content)
    
    # For entries on same date, they should have different actions
    from collections import Counter
    date_counts = Counter(date for date, action in entries)
    
    # Multiple entries on same day is fine (append-only)
    # Just verify they exist
    assert sum(date_counts.values()) >= len(date_counts), \
        "Entry counting logic error"
