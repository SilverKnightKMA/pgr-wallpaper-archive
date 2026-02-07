#!/bin/bash
set -e

# Config
REPO_DIR=$(pwd)
WALLPAPERS_BRANCH=$(node -e "const c=require('./config.json'); console.log(c.wallpapersBranch || 'wallpapers')")
PREVIEW_BRANCH=$(node -e "const c=require('./config.json'); console.log(c.previewBranch || 'preview')")
THUMB_WIDTH=$(node -e "const c=require('./config.json'); console.log(c.settings.thumbnailWidth || 400)")
SERVERS=$(node -e "const c=require('./config.json'); c.servers.forEach(s => console.log(s.id))")

# Git Setup
git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
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
  IMG_DIR="$BRANCH_DIR/images"
  
  # Check if there are new images
  IMAGE_COUNT=0
  if [ -d "$IMG_DIR" ]; then
    IMAGE_COUNT=$(find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | wc -l)
  fi

  if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo "⏭️ No new images for $id."
    continue
  fi

  echo "📂 Processing server: $id ($IMAGE_COUNT new images)"

  # Copy to WP_DIR (Flat structure)
  find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -exec cp {} "$WP_DIR/" \;

  # LFS Tracking
  find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -size +100M | while read -r bigfile; do
    echo "  ⚠️ Large file detected (>100MB): $(basename "$bigfile")"
    git -C "$WP_DIR" lfs track "$(basename "$bigfile")"
  done

  # Copy thumbnails to PV_DIR
  mkdir -p "$PV_DIR/$id/thumbnails"
  if [ -d "$BRANCH_DIR/thumbnails" ]; then
    find "$BRANCH_DIR/thumbnails" -maxdepth 1 -type f -exec cp {} "$PV_DIR/$id/thumbnails/" \;
  fi

  # Check & Generate Missing Thumbnails (Logic simplified using python helper inside loop)
  echo "  🔍 Checking for missing thumbnails..."
  URL_LIST_FILE="$REPO_DIR/Wallpapers/images_url/$id.txt"
  
  # Helper python script to get list of filenames
  FILES_TO_CHECK=$(python3 -c "
import sys, json, urllib.parse, os
files = set()
# From URL list
url_file = '$URL_LIST_FILE'
if os.path.exists(url_file):
    with open(url_file, 'r') as f:
        for line in f:
            if line.strip():
                name = os.path.basename(urllib.parse.unquote(line.strip()))
                files.add(name)
# From Manifest
try:
    m = json.loads('''$MANIFEST''')
    if '$id' in m and 'wallpapers' in m['$id']:
        for w in m['$id']['wallpapers']:
             if w.get('filename'): files.add(w['filename'])
except: pass
for f in files: print(f)
")

  MISSING_COUNT=0
  while IFS= read -r filename; do
     [ -z "$filename" ] && continue
     wpfile="$WP_DIR/$filename"
     thumb_path="$PV_DIR/$id/thumbnails/$filename"
     
     if [ -f "$wpfile" ] && [ ! -f "$thumb_path" ]; then
        convert "$wpfile" -resize "${THUMB_WIDTH}x>" -quality 80 "$thumb_path" 2>/dev/null
        if [ $? -eq 0 ]; then
            MISSING_COUNT=$((MISSING_COUNT + 1))
        else
            echo "    ⚠️ Failed to generate thumbnail: $filename"
        fi
     fi
  done <<< "$FILES_TO_CHECK"
  
  if [ $MISSING_COUNT -gt 0 ]; then
    echo "  ✅ Generated $MISSING_COUNT missing thumbnails."
  fi

done <<< "$SERVERS"

# --- 4. Push Wallpapers ---
git -C "$WP_DIR" add -A
if git -C "$WP_DIR" diff --cached --quiet; then
  echo "  No changes for $WALLPAPERS_BRANCH."
else
  git -C "$WP_DIR" commit -m "Auto-sync: Update wallpapers"
  git -C "$WP_DIR" push origin HEAD:"$WALLPAPERS_BRANCH" --force-with-lease
  echo "  ✅ Pushed to $WALLPAPERS_BRANCH"
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
   # Export env vars needed for node script
   export MANIFEST_PATH="$REPO_DIR/data/manifest.json" 
   export BRANCH_DIR="$WP_DIR" 
   export BRANCH_README_OUTPUT="$PV_DIR/$id/README.md" 
   export FAILED_FILE="$REPO_DIR/Wallpapers/failed/${id}.txt"
   
   node "$REPO_DIR/src/generate_readme.js" branch "$id"
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
