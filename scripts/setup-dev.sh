#!/bin/bash
# Setup development auto-memex skill locally
# Usage: ./scripts/setup-dev.sh

set -e

DEV_DIR="${HOME}/lab/auto-memex"
REMOTE_REPO="hbtjm9000/auto_memex"

# Set up GitHub credentials if GH_TOKEN is provided
if [ -n "$GH_TOKEN" ]; then
    export GIT_AUTH_TOKEN="$GH_TOKEN"
    git config --global credential.helper store
    echo "https://${GH_TOKEN}@github.com" > ~/.git-credentials 2>/dev/null || true
fi

echo "Setting up auto-memex development environment..."

if [ -d "$DEV_DIR/.git" ]; then
    echo "Dev directory already exists at $DEV_DIR"
    cd "$DEV_DIR"
    git pull
else
    echo "Cloning from remote..."
    mkdir -p "$(dirname "$DEV_DIR")"
    git clone "https://github.com/$REMOTE_REPO" "$DEV_DIR"
fi

echo "Development skill ready at: $DEV_DIR"
echo ""
echo "To work on this skill:"
echo "  cd $DEV_DIR"
echo "  # make changes"
echo "  git add . && git commit -m 'changes'"
echo "  git push origin main"