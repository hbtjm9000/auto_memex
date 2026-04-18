#!/bin/bash
# Setup development auto-memex skill locally
# Usage: ./scripts/setup-dev.sh

set -e

DEV_DIR="${HOME}/lab/auto-memex"
REMOTE_URL="https://github.com/hbtjm9000/auto_memex.git"

echo "Setting up auto-memex development environment..."

if [ -d "$DEV_DIR/.git" ]; then
    echo "Dev directory already exists at $DEV_DIR"
    cd "$DEV_DIR"
    git pull origin main
else
    echo "Cloning from remote..."
    mkdir -p "$(dirname "$DEV_DIR")"
    git clone "$REMOTE_URL" "$DEV_DIR"
fi

echo "Development skill ready at: $DEV_DIR"
echo ""
echo "To work on this skill:"
echo "  cd $DEV_DIR"
echo "  # make changes"
echo "  git add . && git commit -m 'changes'"
echo "  git push origin main"