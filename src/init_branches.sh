#!/bin/bash
set -e

# Load config
WALLPAPERS_BRANCH=$(node -e "const c=require('./config.json'); console.log(c.wallpapersBranch || 'wallpapers')")
PREVIEW_BRANCH=$(node -e "const c=require('./config.json'); console.log(c.previewBranch || 'preview')")

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
