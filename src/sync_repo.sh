#!/bin/bash
set -e

# Config
REPO_DIR=$(pwd)
WALLPAPERS_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('wallpapersBranch','wallpapers'))")
SERVERS=$(python3 -c "import json; c=json.load(open('config.json')); [print(s['id']) for s in c['servers']]")
CATEGORIES="desktop mobile"

# Git Setup
git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
git config --global http.postBuffer 524288000
git config --global http.version HTTP/1.1
REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

# --- 1. Prepare Wallpapers Branch ---
echo "⚙️ Preparing $WALLPAPERS_BRANCH branch..."
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

# --- 2. Process Images ---
# Load manifest if exists to check for existing files
MANIFEST="{}"
if [ -f "$REPO_DIR/data/manifest.json" ]; then
  MANIFEST=$(cat "$REPO_DIR/data/manifest.json")
fi
mkdir -p "$REPO_DIR/data"

SERVER_ARGS=""

while IFS= read -r id; do
  SERVER_ARGS="$SERVER_ARGS $id"
  BRANCH_DIR="$REPO_DIR/branches/$id"
  
  # Check if there are new images in any category
  IMAGE_COUNT=0
  for cat in $CATEGORIES; do
    IMG_DIR="$BRANCH_DIR/images/$cat"
    if [ -d "$IMG_DIR" ]; then
      CAT_COUNT=$(find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | wc -l)
      IMAGE_COUNT=$((IMAGE_COUNT + CAT_COUNT))
    fi
  done

  if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo "⏭️ No new images for $id."
    continue
  fi

  echo "📂 Processing server: $id ($IMAGE_COUNT new images)"

  for cat in $CATEGORIES; do
    IMG_DIR="$BRANCH_DIR/images/$cat"
    if [ ! -d "$IMG_DIR" ]; then
      continue
    fi

    CAT_COUNT=$(find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | wc -l)
    if [ "$CAT_COUNT" -eq 0 ]; then
      continue
    fi

    echo "  📁 Category: $cat ($CAT_COUNT files)"

    # Copy to WP_DIR/{category}/
    mkdir -p "$WP_DIR/$cat"
    find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -exec cp {} "$WP_DIR/$cat/" \;

    # LFS Tracking for large files
    find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -size +100M | while read -r bigfile; do
      echo "  ⚠️ Large file detected (>100MB): $(basename "$bigfile")"
      git -C "$WP_DIR" lfs track "$cat/$(basename "$bigfile")"
    done
  done

done <<< "$SERVERS"

# --- 3. Push Wallpapers (Batched) ---
echo "📦 Processing push for $WALLPAPERS_BRANCH..."

# Prevent git from quoting non-ASCII filenames (critical for JP/CN characters)
git -C "$WP_DIR" config core.quotepath false

# Check if there are any changes
if [ -z "$(git -C "$WP_DIR" status --porcelain)" ]; then
  echo "  No changes for $WALLPAPERS_BRANCH."
else
  # Loop while there are uncommitted changes
  while [ -n "$(git -C "$WP_DIR" status --porcelain)" ]; do
    
    # Count remaining files
    REMAINING=$(git -C "$WP_DIR" status --porcelain | wc -l)
    echo "  Processing batch... ($REMAINING files remaining)"

    # Stage the next 200 files
    git -C "$WP_DIR" status --porcelain | head -n 200 | cut -c4- | sed 's/^"//;s/"$//' | while read -r file; do
      git -C "$WP_DIR" add "$file"
    done

    # Commit the current batch
    git -C "$WP_DIR" commit -m "Auto-sync: Batch update ($REMAINING remaining)"

    # Push immediately to clear buffer with retry logic
    ATTEMPT=0
    MAX_RETRIES=5
    PUSH_SUCCESS=false

    while [ $ATTEMPT -lt $MAX_RETRIES ]; do
      if git -C "$WP_DIR" push origin HEAD:"$WALLPAPERS_BRANCH"; then
        PUSH_SUCCESS=true
        break
      else
        ATTEMPT=$((ATTEMPT + 1))
        echo "  ⚠️ Push failed (Attempt $ATTEMPT/$MAX_RETRIES). Retrying in 5s..."
        sleep 5
      fi
    done

    # Exit if push fails after max retries
    if [ "$PUSH_SUCCESS" = false ]; then
      echo "  ❌ Critical error: Failed to push batch to $WALLPAPERS_BRANCH."
      exit 1
    fi

  done
  echo "  ✅ All batches successfully pushed to $WALLPAPERS_BRANCH"
fi

# --- 4. Build Manifest ---
echo ""
echo "📊 Counting images and building manifest..."
MANIFEST=$(printf '%s' "$MANIFEST" | python3 "$REPO_DIR/src/build_manifest.py" "$WP_DIR" "$REPO_DIR" "$RELEASE_TAG_TS" $SERVER_ARGS)
echo "$MANIFEST" > "$REPO_DIR/data/manifest.json"

# --- 5. Generate Per-Server READMEs (into main branch) ---
echo "📝 Generating per-server READMEs..."
while IFS= read -r id; do
   export MANIFEST_PATH="$REPO_DIR/data/manifest.json"
   export BRANCH_DIR="$WP_DIR"
   export BRANCH_README_OUTPUT="$REPO_DIR/servers/$id/README.md"
   export FAILED_DIR="$REPO_DIR/Wallpapers/failed"
   
   python3 "$REPO_DIR/src/generate_readme.py" branch "$id"
done <<< "$SERVERS"

# Cleanup
rm -rf "$WP_DIR"
