#!/bin/bash
set -e

# Config
REPO_DIR=$(pwd)
WALLPAPERS_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('wallpapersBranch','wallpapers'))")
PREVIEW_BRANCH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('previewBranch','preview'))")
THUMB_WIDTH=$(python3 -c "import json; c=json.load(open('config.json')); print(c.get('settings',{}).get('thumbnailWidth',400))")
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

# --- 2. Prepare Preview Branch ---
echo "⚙️ Preparing $PREVIEW_BRANCH branch..."
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

    # Copy thumbnails to PV_DIR
    mkdir -p "$PV_DIR/$id/thumbnails/$cat"
    if [ -d "$BRANCH_DIR/thumbnails/$cat" ]; then
      find "$BRANCH_DIR/thumbnails/$cat" -maxdepth 1 -type f -exec cp {} "$PV_DIR/$id/thumbnails/$cat/" \;
    fi

    # Check & Generate Missing Thumbnails
    echo "  🔍 Checking for missing thumbnails ($cat)..."
    for cat_url_file in "$REPO_DIR/Wallpapers/images_url/${id}_${cat}.txt"; do
      [ -f "$cat_url_file" ] || continue
      while IFS= read -r url; do
        [ -z "$url" ] && continue
        filename=$(python3 -c "import urllib.parse, os, sys; print(os.path.basename(urllib.parse.unquote(sys.argv[1])))" "$url")
        wpfile="$WP_DIR/$cat/$filename"
        thumb_path="$PV_DIR/$id/thumbnails/$cat/$filename"
        
        if [ -f "$wpfile" ] && [ ! -f "$thumb_path" ]; then
          convert "$wpfile" -resize "${THUMB_WIDTH}x>" -quality 80 "$thumb_path" 2>/dev/null || \
            echo "    ⚠️ Failed to generate thumbnail: $filename"
        fi
      done < "$cat_url_file"
    done
  done

done <<< "$SERVERS"

# --- 4. Push Wallpapers (Batched) ---
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

# --- 5. Push Previews ---
git -C "$PV_DIR" add -A
if git -C "$PV_DIR" diff --cached --quiet; then
  echo "  No changes for $PREVIEW_BRANCH."
else
  git -C "$PV_DIR" commit -m "Auto-sync: Update previews"
  git -C "$PV_DIR" push origin HEAD:"$PREVIEW_BRANCH" --force-with-lease
  echo "  ✅ Pushed to $PREVIEW_BRANCH"
fi

# --- 6. Build Manifest ---
echo ""
echo "📊 Counting images and building manifest..."
# Need updated manifest logic
MANIFEST=$(printf '%s' "$MANIFEST" | python3 "$REPO_DIR/src/build_manifest.py" "$WP_DIR" "$REPO_DIR" "$RELEASE_TAG_TS" $SERVER_ARGS)
echo "$MANIFEST" > "$REPO_DIR/data/manifest.json"

# --- 7. Generate READMEs and Update Previews ---
echo "📝 Generating READMEs..."
while IFS= read -r id; do
   # Export env vars needed for python script
   export MANIFEST_PATH="$REPO_DIR/data/manifest.json" 
   export BRANCH_DIR="$WP_DIR" 
   export BRANCH_README_OUTPUT="$PV_DIR/$id/README.md" 
   export FAILED_DIR="$REPO_DIR/Wallpapers/failed"
   
   python3 "$REPO_DIR/src/generate_readme.py" branch "$id"
done <<< "$SERVERS"

# Push README updates
git -C "$PV_DIR" add -A
if ! git -C "$PV_DIR" diff --cached --quiet; then
  git -C "$PV_DIR" commit -m "Auto-sync: Update READMEs"
  git -C "$PV_DIR" push origin HEAD:"$PREVIEW_BRANCH" --force-with-lease
  echo "  ✅ Updated READMEs on $PREVIEW_BRANCH"
fi

# Cleanup
rm -rf "$WP_DIR" "$PV_DIR"
