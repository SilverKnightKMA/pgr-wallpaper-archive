#!/bin/bash
set -e

# Usage: zip_and_release.sh <release_tag>
# Creates multiple complete zip files (each < 1.8GB), uploads each to the
# GitHub release, then deletes the zip and the source images to save disk space.

RELEASE_TAG="$1"
if [ -z "$RELEASE_TAG" ]; then
  echo "❌ Usage: zip_and_release.sh <release_tag>"
  exit 1
fi

MAX_BATCH_BYTES=$((1800 * 1024 * 1024))  # 1.8 GB
WORK_DIR="$(pwd)"
SERVERS=$(python3 -c "import json; c=json.load(open('config.json')); [print(s['id']) for s in c['servers']]")

# --- 1. Collect all new image file paths ---
FILE_LIST=$(mktemp)
trap "rm -f '$FILE_LIST'" EXIT

while IFS= read -r id; do
  txt="new_images/${id}.txt"
  [ -f "$txt" ] || continue

  while IFS= read -r url; do
    [ -z "$url" ] && continue
    fn=$(basename "$url")
    decoded=$(python3 -c "import urllib.parse, sys; print(urllib.parse.unquote(sys.argv[1]))" "$fn")
    filepath="branches/$id/images/$decoded"
    if [ -f "$filepath" ]; then
      # Format: server_id|relative_path
      echo "$id|$filepath" >> "$FILE_LIST"
    fi
  done < "$txt"
done <<< "$SERVERS"

TOTAL=$(wc -l < "$FILE_LIST" | tr -d ' ')
if [ "$TOTAL" -eq 0 ]; then
  echo "⏭️ No files to zip and upload."
  exit 0
fi

echo "📦 Total new image files: $TOTAL"

# --- 2. Batch files into zip parts (each < 1.8 GB) ---
PART=1
BATCH_SIZE=0
STAGING_DIR=$(mktemp -d)
BATCH_SOURCES=$(mktemp)

flush_and_upload() {
  # Check if staging dir has any files
  if [ -z "$(find "$STAGING_DIR" -type f 2>/dev/null)" ]; then
    return
  fi

  local ZIP_NAME="${RELEASE_TAG}-part${PART}.zip"
  echo ""
  echo "📦 Creating ${ZIP_NAME}..."
  (cd "$STAGING_DIR" && zip -r "${WORK_DIR}/${ZIP_NAME}" .)

  echo "📤 Uploading ${ZIP_NAME}..."
  local ATTEMPT=0
  local MAX_RETRIES=3
  local UPLOAD_OK=false

  while [ $ATTEMPT -lt $MAX_RETRIES ]; do
    if gh release upload "$RELEASE_TAG" "${WORK_DIR}/${ZIP_NAME}" --clobber; then
      UPLOAD_OK=true
      break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "  ⚠️ Upload failed (attempt ${ATTEMPT}/${MAX_RETRIES}). Retrying in 10s..."
    sleep 10
  done

  if [ "$UPLOAD_OK" = false ]; then
    echo "  ❌ Failed to upload ${ZIP_NAME} after ${MAX_RETRIES} retries."
    exit 1
  fi

  # Delete the zip file
  rm -f "${WORK_DIR}/${ZIP_NAME}"

  # Delete source images that were included in this batch
  while IFS= read -r src; do
    [ -z "$src" ] && continue
    rm -f "$src"
  done < "$BATCH_SOURCES"

  # Clean up staging & batch list for next iteration
  rm -rf "${STAGING_DIR:?}"/*
  > "$BATCH_SOURCES"

  echo "  ✅ Part ${PART} uploaded and cleaned up."
  PART=$((PART + 1))
  BATCH_SIZE=0
}

while IFS='|' read -r id filepath; do
  [ -z "$filepath" ] && continue

  filesize=$(stat -c%s "$filepath" 2>/dev/null || echo 0)

  # If adding this file would exceed limit and batch is not empty, flush first
  if [ "$BATCH_SIZE" -gt 0 ] && [ $((BATCH_SIZE + filesize)) -gt $MAX_BATCH_BYTES ]; then
    flush_and_upload
  fi

  # Copy file into staging (flat – no server sub-directories)
  cp "$filepath" "$STAGING_DIR/"
  echo "$filepath" >> "$BATCH_SOURCES"
  BATCH_SIZE=$((BATCH_SIZE + filesize))

done < "$FILE_LIST"

# Flush remaining batch
flush_and_upload

# Clean up temp files
rm -f "$FILE_LIST" "$BATCH_SOURCES"
rm -rf "$STAGING_DIR"

echo ""
echo "✅ All $((PART - 1)) part(s) uploaded to release ${RELEASE_TAG}."
