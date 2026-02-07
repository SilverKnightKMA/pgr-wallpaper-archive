#!/bin/bash
# Generate thumbnails for images in a directory
# Usage: ./generate_thumbnails.sh <source_dir> <thumb_width>
#
# Requires: ImageMagick (convert)

SOURCE_DIR="$1"
THUMB_WIDTH="${2:-400}"
THUMB_DIR="${SOURCE_DIR}/thumbnails"

if [ -z "$SOURCE_DIR" ] || [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Source directory not found: $SOURCE_DIR"
    exit 1
fi

mkdir -p "$THUMB_DIR"

count=0
while read -r img; do
    filename=$(basename "$img")
    thumb_path="${THUMB_DIR}/${filename}"

    if [ -f "$thumb_path" ]; then
        continue
    fi

    convert "$img" -resize "${THUMB_WIDTH}x>" -quality 80 "$thumb_path" 2>/dev/null
    if [ $? -eq 0 ]; then
        count=$((count + 1))
    else
        echo "⚠️ Failed to create thumbnail for: $filename"
    fi
done < <(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \))

echo "✅ Generated $count new thumbnails in $THUMB_DIR"
