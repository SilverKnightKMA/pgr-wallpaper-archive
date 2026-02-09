#!/bin/bash
set -e

# Load config
WALLPAPERS_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('wallpapersBranch','wallpapers'))")
PREVIEW_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('previewBranch','preview'))")

git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

# Initialize wallpapers branch
if git ls-remote --exit-code origin "$WALLPAPERS_BRANCH" >/dev/null 2>&1; then
  echo "Branch $WALLPAPERS_BRANCH already exists."
else
  echo "Creating new orphan branch: $WALLPAPERS_BRANCH"
  INIT_DIR=$(mktemp -d)
  git -C "$INIT_DIR" init -q
  git -C "$INIT_DIR" remote add origin "$REMOTE_URL"
  git -C "$INIT_DIR" checkout -q -b "$WALLPAPERS_BRANCH"
  git -C "$INIT_DIR" commit -q --allow-empty -m "Initialize branch $WALLPAPERS_BRANCH"
  git -C "$INIT_DIR" push -q origin "$WALLPAPERS_BRANCH"
  rm -rf "$INIT_DIR"
  echo "  Branch $WALLPAPERS_BRANCH created."
fi

# Initialize preview branch
if git ls-remote --exit-code origin "$PREVIEW_BRANCH" >/dev/null 2>&1; then
  echo "Branch $PREVIEW_BRANCH already exists."
else
  echo "Creating new orphan branch: $PREVIEW_BRANCH"
  INIT_DIR=$(mktemp -d)
  git -C "$INIT_DIR" init -q
  git -C "$INIT_DIR" remote add origin "$REMOTE_URL"
  git -C "$INIT_DIR" checkout -q -b "$PREVIEW_BRANCH"
  git -C "$INIT_DIR" commit -q --allow-empty -m "Initialize branch $PREVIEW_BRANCH"
  git -C "$INIT_DIR" push -q origin "$PREVIEW_BRANCH"
  rm -rf "$INIT_DIR"
  echo "  Branch $PREVIEW_BRANCH created."
fi
