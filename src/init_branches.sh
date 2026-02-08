#!/bin/bash
set -e

# Load config
WALLPAPERS_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('wallpapersBranch','wallpapers'))")
PREVIEW_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('previewBranch','preview'))")

git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

for BRANCH_NAME in "$WALLPAPERS_BRANCH" "$PREVIEW_BRANCH"; do
  if git ls-remote --exit-code origin "$BRANCH_NAME" >/dev/null 2>&1; then
    echo "✅ Branch $BRANCH_NAME already exists."
  else
    echo "🆕 Creating new orphan branch: $BRANCH_NAME"
    INIT_DIR=$(mktemp -d)
    git -C "$INIT_DIR" init
    git -C "$INIT_DIR" remote add origin "$REMOTE_URL"
    git -C "$INIT_DIR" checkout -b "$BRANCH_NAME"
    git -C "$INIT_DIR" commit --allow-empty -m "Initialize branch $BRANCH_NAME"
    git -C "$INIT_DIR" push origin "$BRANCH_NAME"
    rm -rf "$INIT_DIR"
    echo "  ✅ Branch $BRANCH_NAME created."
  fi
done
