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

if [ -z "$(git -C "$WP_DIR" status --porcelain)" ]; then
  echo "  No changes for $WALLPAPERS_BRANCH."
else
  while [ -n "$(git -C "$WP_DIR" status --porcelain)" ]; do
    REMAINING=$(git -C "$WP_DIR" status --porcelain | wc -l)
    echo "  Processing batch... ($REMAINING files remaining)"

    git -C "$WP_DIR" status --porcelain | head -n 200 | cut -c4- | sed 's/^"//;s/"$//' | while read -r file; do
      git -C "$WP_DIR" add "$file"
    done

    git -C "$WP_DIR" commit -m "Auto-sync: Batch update ($REMAINING remaining)"

    ATTEMPT=0
    MAX_RETRIES=5
    PUSH_SUCCESS=false

    while [ $ATTEMPT -lt $MAX_RETRIES ]; do
      if git -C "$WP_DIR" push origin HEAD:"$WALLPAPERS_BRANCH"; then
        PUSH_SUCCESS=true
        break
      else
        ATTEMPT=$((ATTEMPT + 1))
        echo "  Push failed (Attempt $ATTEMPT/$MAX_RETRIES). Retrying in 5s..."
        sleep 5
      fi
    done

    if [ "$PUSH_SUCCESS" = false ]; then
      echo "  Critical error: Failed to push batch to $WALLPAPERS_BRANCH."
      exit 1
    fi
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

if [ -z "$(git -C "$PV_DIR" status --porcelain)" ]; then
  echo "  No changes for $PREVIEW_BRANCH."
else
  while [ -n "$(git -C "$PV_DIR" status --porcelain)" ]; do
    REMAINING=$(git -C "$PV_DIR" status --porcelain | wc -l)
    echo "  Processing batch... ($REMAINING files remaining)"

    git -C "$PV_DIR" status --porcelain | head -n 500 | cut -c4- | sed 's/^"//;s/"$//' | while read -r file; do
      git -C "$PV_DIR" add "$file"
    done

    git -C "$PV_DIR" commit -m "Auto-sync: Preview update ($REMAINING remaining)"

    ATTEMPT=0
    MAX_RETRIES=5
    PUSH_SUCCESS=false

    while [ $ATTEMPT -lt $MAX_RETRIES ]; do
      if git -C "$PV_DIR" push origin HEAD:"$PREVIEW_BRANCH"; then
        PUSH_SUCCESS=true
        break
      else
        ATTEMPT=$((ATTEMPT + 1))
        echo "  Push failed (Attempt $ATTEMPT/$MAX_RETRIES). Retrying in 5s..."
        sleep 5
      fi
    done

    if [ "$PUSH_SUCCESS" = false ]; then
      echo "  Critical error: Failed to push batch to $PREVIEW_BRANCH."
      exit 1
    fi
  done
  echo "  All batches pushed to $PREVIEW_BRANCH"
fi

# Cleanup
rm -rf "$WP_DIR" "$PV_DIR"
