#!/bin/bash
set -e

# Load config
WALLPAPERS_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('wallpapersBranch','wallpapers'))")

git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

if git ls-remote --exit-code origin "$WALLPAPERS_BRANCH" >/dev/null 2>&1; then
  echo "✅ Branch $WALLPAPERS_BRANCH already exists."
else
  echo "🆕 Creating new orphan branch: $WALLPAPERS_BRANCH"
  INIT_DIR=$(mktemp -d)
  git -C "$INIT_DIR" init
  git -C "$INIT_DIR" remote add origin "$REMOTE_URL"
  git -C "$INIT_DIR" checkout -b "$WALLPAPERS_BRANCH"
  git -C "$INIT_DIR" commit --allow-empty -m "Initialize branch $WALLPAPERS_BRANCH"
  git -C "$INIT_DIR" push origin "$WALLPAPERS_BRANCH"
  rm -rf "$INIT_DIR"
  echo "  ✅ Branch $WALLPAPERS_BRANCH created."
fi
