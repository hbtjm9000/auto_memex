#!/bin/bash
# lint_watcher.sh - Real-time vault linter using inotifywait
# Auto-fixes rules 3 (index), 5 (stale), 6 (tag taxonomy) on every vault change.
# Writes full reports to vault/lint.log.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
LINT_SCRIPT="$SKILL_DIR/scripts/lint_wiki.py"
VAULT="/home/hbtjm/library"
LOG_FILE="$VAULT/lint.log"
PID_FILE="/tmp/lint_watcher.pid"

DEBOUNCE_SECS=5   # seconds to wait after last change before linting

# ── Commands ────────────────────────────────────────────────────────────────

start() {
    if status &>/dev/null; then
        echo "Watcher already running (PID $(cat "$PID_FILE"))"
        return 0
    fi

    if ! command -v inotifywait &>/dev/null; then
        echo "ERROR: inotifywait not found. Install inotify-tools." >&2
        return 1
    fi

    mkdir -p "$(dirname "$PID_FILE")"

    # Start inotifywait in monitor mode, debounce, then run lint --fix
    inotifywait -m -r -e modify,create,delete,move "$VAULT" \
        --format '%w%f' \
        2>/dev/null \
        | while read -r path; do
            # Skip git internal files and lint.log to avoid feedback loops
            if [[ "$path" == *".git/"* ]] || [[ "$path" == *"/lint.log"* ]]; then
                continue
            fi
            # Debounce: wait for burst to settle
            sleep "$DEBOUNCE_SECS"
            # Drain any additional events that arrived during sleep
            inotifywait -t 1 -e modify,create,delete,move "$VAULT" \
                --format '%w%f' 2>/dev/null || true
            run_lint
        done &

    local pid=$!
    echo $pid > "$PID_FILE"
    echo "Watcher started (PID $pid). Vault: $VAULT"
}

stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "Watcher not running."
        return 0
    fi
    local pid
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" && rm -f "$PID_FILE" && echo "Watcher stopped."
    else
        rm -f "$PID_FILE" && echo "Stale PID file removed."
    fi
}

status() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "Watcher not running."
        return 1
    fi
    local pid
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "Watcher running (PID $pid)."
        return 0
    else
        echo "Watcher not running (stale PID $pid)."
        rm -f "$PID_FILE"
        return 1
    fi
}

run_lint() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local output
    output=$(python3 "$LINT_SCRIPT" --vault "$VAULT" --fix --no-log 2>&1) || true
    {
        echo "=== [$timestamp] lint_watcher run ==="
        echo "$output"
        echo ""
    } >> "$LOG_FILE"
}

# ── Main ───────────────────────────────────────────────────────────────────

case "${1:-status}" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
    run)    run_lint ;;
    *)      echo "Usage: $0 {start|stop|status|run}" >&2; exit 1 ;;
esac
