#!/bin/bash
# Setup production auto-memex skill from git remote
# Usage: ./scripts/setup-prod.sh

set -e

PROD_DIR="${HOME}/.paradigm/hermes/auto-memex"
REMOTE_REPO="hbtjm9000/auto_memex"

echo "Setting up auto-memex production skill..."

if [ -d "$PROD_DIR/.git" ]; then
    echo "Production directory exists. Pulling latest..."
    cd "$PROD_DIR"
    git pull
else
    echo "Cloning from remote to production..."
    mkdir -p "$(dirname "$PROD_DIR")"
    gh repo clone "$REMOTE_REPO" "$PROD_DIR" -- --origin origin || git clone "https://github.com/$REMOTE_REPO" "$PROD_DIR"
fi

echo "Production skill ready at: $PROD_DIR"
echo ""
echo "Add to ~/.hermes/config.yaml:"
echo "  skills:"
echo "    external_dirs:"
echo "      - $PROD_DIR"