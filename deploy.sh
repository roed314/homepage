#!/bin/bash
# Deploy the generated site to laurent.mit.edu via the lovelace jump host.
#
# Setup (once): add to ~/.ssh/config
#   Host laurent
#     HostName laurent.mit.edu
#     User roed
#     ProxyJump roed@lovelace.mit.edu
#
# REMOTE_DIR must point at the directory served as math.mit.edu/~roed/.
# rsync is run WITHOUT --delete: files that exist on the server but not in
# site/ (writings/, courses/, conferences/*/, old stylesheets, ...) are left
# alone.  Only files the build produces are created or overwritten.

set -euo pipefail
cd "$(dirname "$0")"

REMOTE=laurent
REMOTE_DIR=www   # <-- adjust to the real web root before first use

if [ -n "$(git status --porcelain)" ]; then
    echo "Working tree has uncommitted changes; commit before deploying."
    echo "(override with deploy.sh --force)"
    if [ "${1:-}" != "--force" ]; then
        exit 1
    fi
fi

rsync -avz --no-perms --omit-dir-times site/ "$REMOTE:$REMOTE_DIR/"
echo "Deployed.  Remember to git push."
