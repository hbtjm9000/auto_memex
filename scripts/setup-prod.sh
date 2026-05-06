#!/bin/bash
# Setup production auto-memex skill from git remote
# Usage: ./scripts/setup-prod.sh

set -e

PROD_DIR="${HOME}/.paradigm/hermes/auto-memex"
REMOTE_REPO="hbtjm9000/auto_memex"

# Set up GitHub credentials if GH_TOKEN is provided
if [ -n "$GH_TOKEN" ]; then
    export GIT_AUTH_TOKEN="$GH_TOKEN"
    export GIT_ASKPASS="/bin/echo"
    export GCM_INTERACTIVE="false"
    git config --global credential.helper store
    echo "https://${GH_TOKEN}@github.com" > ~/.git-credentials 2>/dev/null || true
fi

echo "Setting up auto-memex production skill..."

if [ -d "$PROD_DIR/.git" ]; then
    echo "Production directory exists. Pulling latest..."
    cd "$PROD_DIR"
    git pull
else
    echo "Cloning from remote to production..."
    mkdir -p "$(dirname "$PROD_DIR")"
    if command -v gh &>/dev/null && [ -z "$GH_TOKEN" ]; then
        gh repo clone "$REMOTE_REPO" "$PROD_DIR" -- --origin origin
    else
        git clone "https://github.com/$REMOTE_REPO" "$PROD_DIR"
    fi
fi

echo "Production skill ready at: $PROD_DIR"
echo ""
echo "Add to ~/.hermes/config.yaml:"
echo "  skills:"
echo "    external_dirs:"
echo "      - $PROD_DIR"