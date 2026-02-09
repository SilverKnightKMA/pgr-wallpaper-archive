#!/bin/bash
set -e

# Config
REPO_DIR=$(pwd)
WALLPAPERS_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('wallpapersBranch','wallpapers'))")
PREVIEW_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('previewBranch','preview'))")
SERVERS=$(python3 -c "import json; c=json.load(open('config.json')); [print(s['id']) for s in c['servers']]")
CATEGORIES="desktop mobile"

# Git Setup
git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
git config --global http.postBuffer 524288000
git config --global http.version HTTP/1.1
REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

# --- 1. Prepare Wallpapers Branch ---
echo "Preparing $WALLPAPERS_BRANCH branch..."
WP_DIR="$(mktemp -d)/repo_wp"
git init "$WP_DIR"
git -C "$WP_DIR" remote add origin "$REMOTE_URL"
if git ls-remote --exit-code origin "$WALLPAPERS_BRANCH" >/dev/null 2>&1; then
  git -C "$WP_DIR" fetch origin "$WALLPAPERS_BRANCH" --depth=1
  git -C "$WP_DIR" checkout -b "$WALLPAPERS_BRANCH" "origin/$WALLPAPERS_BRANCH"
else
  git -C "$WP_DIR" checkout -b "$WALLPAPERS_BRANCH"
fi
git -C "$WP_DIR" lfs install --local

# Ensure desktop/mobile dirs exist in WP_DIR
mkdir -p "$WP_DIR/desktop" "$WP_DIR/mobile"

# --- 2. Prepare Preview Branch ---
echo "Preparing $PREVIEW_BRANCH branch..."
PV_DIR="$(mktemp -d)/repo_pv"
git init "$PV_DIR"
git -C "$PV_DIR" remote add origin "$REMOTE_URL"
if git ls-remote --exit-code origin "$PREVIEW_BRANCH" >/dev/null 2>&1; then
  git -C "$PV_DIR" fetch origin "$PREVIEW_BRANCH" --depth=1
  git -C "$PV_DIR" checkout -b "$PREVIEW_BRANCH" "origin/$PREVIEW_BRANCH"
else
  git -C "$PV_DIR" checkout -b "$PREVIEW_BRANCH"
fi

# --- 3. Process Images ---
MANIFEST="{}"
if [ -f "$REPO_DIR/data/manifest.json" ]; then
  MANIFEST=$(cat "$REPO_DIR/data/manifest.json")
fi
mkdir -p "$REPO_DIR/data"

SERVER_ARGS=""

while IFS= read -r id; do
  SERVER_ARGS="$SERVER_ARGS $id"
  BRANCH_DIR="$REPO_DIR/branches/$id"

  # Check if there are new images in the organized category dirs
  IMAGE_COUNT=0
  for cat in $CATEGORIES; do
    IMG_DIR="$BRANCH_DIR/images/$cat"
    if [ -d "$IMG_DIR" ]; then
      CAT_COUNT=$(find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | wc -l)
      IMAGE_COUNT=$((IMAGE_COUNT + CAT_COUNT))
    fi
  done

  if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo "No new images for $id."
    continue
  fi

  echo "Processing server: $id ($IMAGE_COUNT new images)"

  # Copy originals to WP_DIR/{category}/
  for cat in $CATEGORIES; do
    IMG_DIR="$BRANCH_DIR/images/$cat"
    if [ ! -d "$IMG_DIR" ]; then
      continue
    fi

    CAT_COUNT=$(find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | wc -l)
    if [ "$CAT_COUNT" -eq 0 ]; then
      continue
    fi

    echo "  Category: $cat ($CAT_COUNT files)"

    mkdir -p "$WP_DIR/$cat"
    find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -exec cp {} "$WP_DIR/$cat/" \;

    # LFS Tracking for large files
    find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -size +100M | while read -r bigfile; do
      echo "  Large file detected (>100MB): $(basename "$bigfile")"
      git -C "$WP_DIR" lfs track "$cat/$(basename "$bigfile")"
    done
  done

  # Copy previews to PV_DIR/previews/ subdirectory
  PREVIEW_DIR="$BRANCH_DIR/previews"
  if [ -d "$PREVIEW_DIR" ]; then
    PREVIEW_COUNT=$(find "$PREVIEW_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | wc -l)
    if [ "$PREVIEW_COUNT" -gt 0 ]; then
      echo "  Previews: $PREVIEW_COUNT files"
      mkdir -p "$PV_DIR/previews"
      find "$PREVIEW_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) -exec cp {} "$PV_DIR/previews/" \;
    fi
  fi

done <<< "$SERVERS"

# --- 4. Generate previews for existing images in WP_DIR ---
echo ""
echo "Generating previews for all images in wallpapers branch..."
mkdir -p "$PV_DIR/previews"
python3 "$REPO_DIR/src/process_images.py" --wp-dir "$WP_DIR" --preview-dir "$PV_DIR/previews"

# --- 5. Push Wallpapers Branch (Batched) ---
echo ""
echo "Processing push for $WALLPAPERS_BRANCH..."

git -C "$WP_DIR" config core.quotepath false

# Push helper with exponential backoff
push_with_retry() {
  local DIR="$1"
  local BRANCH="$2"
  local MAX_RETRIES=7
  local ATTEMPT=0
  local DELAY=10

  while [ $ATTEMPT -lt $MAX_RETRIES ]; do
    # Push LFS objects first (separate step to avoid timeouts)
    if git -C "$DIR" lfs push origin HEAD 2>/dev/null; then
      echo "  LFS objects pushed successfully."
    fi

    if git -C "$DIR" push origin HEAD:"$BRANCH"; then
      return 0
    else
      ATTEMPT=$((ATTEMPT + 1))
      # Exponential backoff: 10, 20, 40, 80, 160, 320, 640
      echo "  Push failed (Attempt $ATTEMPT/$MAX_RETRIES). Retrying in ${DELAY}s..."
      sleep $DELAY
      DELAY=$((DELAY * 2))
    fi
  done
  return 1
}

WP_BATCH_SIZE=40

if [ -z "$(git -C "$WP_DIR" status --porcelain)" ]; then
  echo "  No changes for $WALLPAPERS_BRANCH."
else
  while [ -n "$(git -C "$WP_DIR" status --porcelain)" ]; do
    REMAINING=$(git -C "$WP_DIR" status --porcelain | wc -l)
    BATCH_N=$((REMAINING < WP_BATCH_SIZE ? REMAINING : WP_BATCH_SIZE))
    echo "  Processing batch of $BATCH_N... ($REMAINING files remaining)"

    git -C "$WP_DIR" status --porcelain | head -n "$WP_BATCH_SIZE" | cut -c4- | sed 's/^"//;s/"$//' | while read -r file; do
      git -C "$WP_DIR" add "$file"
    done

    git -C "$WP_DIR" commit -m "Auto-sync: Batch update ($REMAINING remaining)"

    if ! push_with_retry "$WP_DIR" "$WALLPAPERS_BRANCH"; then
      echo "  Critical error: Failed to push batch to $WALLPAPERS_BRANCH."
      exit 1
    fi

    # Small delay between successful pushes to avoid rate limiting
    sleep 3
  done
  echo "  All batches pushed to $WALLPAPERS_BRANCH"
fi

# --- 6. Build Manifest ---
echo ""
echo "Building manifest..."
MANIFEST=$(printf '%s' "$MANIFEST" | python3 "$REPO_DIR/src/build_manifest.py" "$WP_DIR" "$REPO_DIR" "$RELEASE_TAG_TS" $SERVER_ARGS)
echo "$MANIFEST" > "$REPO_DIR/data/manifest.json"

# --- 7. Generate Per-Server READMEs (into preview branch) ---
echo "Generating per-server READMEs for preview branch..."
while IFS= read -r id; do
   export MANIFEST_PATH="$REPO_DIR/data/manifest.json"
   export PREVIEW_DIR="$PV_DIR"
   export BRANCH_README_OUTPUT="$PV_DIR/$id/README.md"
   export FAILED_DIR="$REPO_DIR/Wallpapers/failed"

   mkdir -p "$PV_DIR/$id"
   python3 "$REPO_DIR/src/generate_readme.py" branch "$id"
done <<< "$SERVERS"

# --- 8. Push Preview Branch ---
echo ""
echo "Processing push for $PREVIEW_BRANCH..."

git -C "$PV_DIR" config core.quotepath false

PV_BATCH_SIZE=200

if [ -z "$(git -C "$PV_DIR" status --porcelain)" ]; then
  echo "  No changes for $PREVIEW_BRANCH."
else
  while [ -n "$(git -C "$PV_DIR" status --porcelain)" ]; do
    REMAINING=$(git -C "$PV_DIR" status --porcelain | wc -l)
    BATCH_N=$((REMAINING < PV_BATCH_SIZE ? REMAINING : PV_BATCH_SIZE))
    echo "  Processing batch of $BATCH_N... ($REMAINING files remaining)"

    git -C "$PV_DIR" status --porcelain | head -n "$PV_BATCH_SIZE" | cut -c4- | sed 's/^"//;s/"$//' | while read -r file; do
      git -C "$PV_DIR" add "$file"
    done

    git -C "$PV_DIR" commit -m "Auto-sync: Preview update ($REMAINING remaining)"

    if ! push_with_retry "$PV_DIR" "$PREVIEW_BRANCH"; then
      echo "  Critical error: Failed to push batch to $PREVIEW_BRANCH."
      exit 1
    fi

    sleep 2
  done
  echo "  All batches pushed to $PREVIEW_BRANCH"
fi

# Cleanup
rm -rf "$WP_DIR" "$PV_DIR"
