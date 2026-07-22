#!/bin/sh
# One-time setup: put this site on GitHub Pages (free, permanent URL).
#
#   1. Install the GitHub CLI:   brew install gh
#   2. Log in:                   gh auth login
#   3. Run this script:          ./deploy.sh
#
# After that, the "Publish to the web" button in Studio pushes updates.

set -e
cd "$(dirname "$0")"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI not found. Run:  brew install gh   then:  gh auth login"
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "Not logged in to GitHub. Run:  gh auth login"
  exit 1
fi

# Repo named <username>.github.io = the site lives at the clean root URL
# (https://<username>.github.io/) with nothing after the slash.
USER="$(gh api user -q .login)"
REPO="$USER.github.io"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -b main
fi
git add -A
git commit -m "Portfolio" || true

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$REPO" --public --source=. --remote=origin --push
else
  git push -u origin main
fi

# enable GitHub Pages from the main branch root
gh api "repos/$USER/$REPO/pages" --method POST \
  -f "source[branch]=main" -f "source[path]=/" 2>/dev/null \
  || echo "(Pages may already be enabled - that's fine)"

echo
echo "Done. Your site will be live in ~1 minute at:"
echo "  https://$USER.github.io/"
