#!/usr/bin/env python3
"""Process downloaded images: detect resolution, categorize, generate previews.

For each downloaded image:
  1. Detect resolution (width x height) using Pillow
  2. Determine category: landscape (width >= height) → desktop, portrait → mobile
  3. Generate a small preview/thumbnail for the preview branch
  4. Move original to branches/<server>/images/<category>/
  5. Save preview to branches/<server>/previews/<filename>

Outputs:
  - Organized images in branches/<server>/images/{desktop,mobile}/
  - Preview thumbnails in branches/<server>/previews/
  - data/image_metadata.json with resolution + category data

Usage:
    python3 src/process_images.py

Also supports processing images already in WP_DIR (wallpapers branch checkout)
to generate metadata for existing images without previews:
    python3 src/process_images.py --wp-dir <path>
"""

import json
import os
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(SCRIPT_DIR, '..')
CONFIG_PATH = os.path.join(REPO_DIR, 'config.json')

# Preview settings
PREVIEW_MAX_SIZE = 480  # Max dimension (width or height) for preview
PREVIEW_QUALITY = 85    # JPEG quality for previews

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def load_config():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


def get_image_resolution(filepath):
    """Get image resolution (width, height) using Pillow.

    Returns (width, height) or (0, 0) on failure.
    """
    try:
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception as e:
        print(f"  Warning: Could not read image {os.path.basename(filepath)}: {e}",
              file=sys.stderr)
        return (0, 0)


def determine_category(width, height):
    """Determine category based on resolution.

    landscape (width >= height) → desktop
    portrait (width < height) → mobile
    """
    if width <= 0 or height <= 0:
        return 'desktop'  # fallback
    return 'desktop' if width >= height else 'mobile'


def generate_preview(src_path, dest_path, max_size=PREVIEW_MAX_SIZE,
                     quality=PREVIEW_QUALITY):
    """Generate a preview/thumbnail image.

    Resizes to fit within max_size while preserving aspect ratio.
    Saves as JPEG for consistent smaller file sizes.
    """
    try:
        with Image.open(src_path) as img:
            # Convert to RGB if necessary (for PNG with alpha, etc.)
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')

            # Calculate new size preserving aspect ratio
            w, h = img.size
            if w > max_size or h > max_size:
                if w >= h:
                    new_w = max_size
                    new_h = int(h * max_size / w)
                else:
                    new_h = max_size
                    new_w = int(w * max_size / h)
                img = img.resize((new_w, new_h), Image.LANCZOS)

            # Save as JPEG
            # Change extension to .jpg for previews
            base, ext = os.path.splitext(dest_path)
            dest_path_jpg = base + '.jpg'
            img.save(dest_path_jpg, 'JPEG', quality=quality, optimize=True)
            return dest_path_jpg
    except Exception as e:
        print(f"  Warning: Could not generate preview for {os.path.basename(src_path)}: {e}",
              file=sys.stderr)
        return None


def process_single_image(filepath, server_id, images_base_dir, previews_dir):
    """Process a single image: get resolution, determine category, generate preview.

    Returns dict with metadata, or None on failure.
    """
    filename = os.path.basename(filepath)
    width, height = get_image_resolution(filepath)
    category = determine_category(width, height)

    # Move original to category directory
    cat_dir = os.path.join(images_base_dir, category)
    os.makedirs(cat_dir, exist_ok=True)
    dest_path = os.path.join(cat_dir, filename)

    if filepath != dest_path:
        shutil.move(filepath, dest_path)

    # Generate preview
    os.makedirs(previews_dir, exist_ok=True)
    preview_dest = os.path.join(previews_dir, filename)
    preview_path = generate_preview(dest_path, preview_dest)

    # Build preview filename (always .jpg)
    preview_filename = None
    if preview_path:
        preview_filename = os.path.basename(preview_path)

    return {
        'filename': filename,
        'width': width,
        'height': height,
        'resolution': f'{width}x{height}' if width > 0 and height > 0 else '',
        'category': category,
        'preview': preview_filename,
    }


def process_server_downloads(server_id):
    """Process all downloaded images for a server."""
    downloads_dir = os.path.join(REPO_DIR, 'branches', server_id, 'downloads')
    images_dir = os.path.join(REPO_DIR, 'branches', server_id, 'images')
    previews_dir = os.path.join(REPO_DIR, 'branches', server_id, 'previews')

    if not os.path.isdir(downloads_dir):
        return {}

    # Find all image files
    files = [f for f in os.listdir(downloads_dir)
             if f.lower().endswith(IMAGE_EXTENSIONS) and os.path.isfile(os.path.join(downloads_dir, f))]

    if not files:
        return {}

    print(f'  Processing {len(files)} images for {server_id}...')
    metadata = {}

    for filename in files:
        filepath = os.path.join(downloads_dir, filename)
        result = process_single_image(filepath, server_id, images_dir, previews_dir)
        if result:
            metadata[filename] = result
            cat_icon = '🖥️' if result['category'] == 'desktop' else '📱'
            print(f'    {cat_icon} {filename}: {result["resolution"]} → {result["category"]}')

    print(f'  Done: {len(metadata)} images processed for {server_id}')
    return metadata


def process_wp_dir_images(wp_dir):
    """Process existing images in the wallpapers branch checkout.

    This is used to generate resolution metadata for images that already
    exist in the wallpapers branch but don't have resolution data yet.
    Does NOT move files or generate previews (those are already organized).

    Returns metadata dict keyed by filename.
    """
    metadata = {}
    categories = ['desktop', 'mobile']

    for cat in categories:
        cat_dir = os.path.join(wp_dir, cat)
        if not os.path.isdir(cat_dir):
            continue

        files = [f for f in os.listdir(cat_dir)
                 if f.lower().endswith(IMAGE_EXTENSIONS) and os.path.isfile(os.path.join(cat_dir, f))]

        for filename in files:
            filepath = os.path.join(cat_dir, filename)
            width, height = get_image_resolution(filepath)

            # Use actual resolution to determine category
            # (may differ from the directory it's currently in)
            actual_category = determine_category(width, height)

            metadata[filename] = {
                'filename': filename,
                'width': width,
                'height': height,
                'resolution': f'{width}x{height}' if width > 0 and height > 0 else '',
                'category': actual_category,
                'current_category': cat,  # where it currently lives
                'preview': None,
            }

    return metadata


def generate_previews_for_wp_dir(wp_dir, preview_dir):
    """Generate preview thumbnails for ALL images in wallpapers branch.

    This handles both new and existing images.
    """
    categories = ['desktop', 'mobile']
    count = 0

    for cat in categories:
        cat_dir = os.path.join(wp_dir, cat)
        if not os.path.isdir(cat_dir):
            continue

        files = [f for f in os.listdir(cat_dir)
                 if f.lower().endswith(IMAGE_EXTENSIONS) and os.path.isfile(os.path.join(cat_dir, f))]

        for filename in files:
            filepath = os.path.join(cat_dir, filename)
            preview_dest = os.path.join(preview_dir, filename)

            # Skip if preview already exists
            base, ext = os.path.splitext(preview_dest)
            preview_jpg = base + '.jpg'
            if os.path.isfile(preview_jpg):
                continue

            result = generate_preview(filepath, preview_dest)
            if result:
                count += 1

    return count


def main():
    config = load_config()
    servers = config.get('servers', [])

    # Check for --wp-dir mode (process existing wallpapers branch)
    if '--wp-dir' in sys.argv:
        idx = sys.argv.index('--wp-dir')
        if idx + 1 < len(sys.argv):
            wp_dir = sys.argv[idx + 1]
            print(f'=== PROCESSING EXISTING IMAGES IN {wp_dir} ===')

            metadata = process_wp_dir_images(wp_dir)
            print(f'Processed {len(metadata)} existing images')

            # Also generate previews if --preview-dir is specified
            if '--preview-dir' in sys.argv:
                pidx = sys.argv.index('--preview-dir')
                if pidx + 1 < len(sys.argv):
                    preview_dir = sys.argv[pidx + 1]
                    os.makedirs(preview_dir, exist_ok=True)
                    count = generate_previews_for_wp_dir(wp_dir, preview_dir)
                    print(f'Generated {count} new previews')

            # Save metadata
            metadata_path = os.path.join(REPO_DIR, 'data', 'image_metadata.json')
            os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

            # Merge with existing metadata
            existing_metadata = {}
            if os.path.isfile(metadata_path):
                with open(metadata_path, encoding='utf-8') as f:
                    existing_metadata = json.load(f)

            existing_metadata.update(metadata)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(existing_metadata, f, ensure_ascii=False, indent=2)
            print(f'Metadata saved to {metadata_path}')
            return

    # Normal mode: process newly downloaded images
    print('=== PROCESS IMAGES: Resolution Detection + Preview Generation ===')

    all_metadata = {}
    for server in servers:
        server_id = server['id']
        server_name = server['name']
        print(f'\n--- {server_name} ---')

        metadata = process_server_downloads(server_id)
        all_metadata.update(metadata)

    # Save combined image metadata
    metadata_path = os.path.join(REPO_DIR, 'data', 'image_metadata.json')
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

    # Merge with existing metadata if present
    existing_metadata = {}
    if os.path.isfile(metadata_path):
        try:
            with open(metadata_path, encoding='utf-8') as f:
                existing_metadata = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    existing_metadata.update(all_metadata)
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(existing_metadata, f, ensure_ascii=False, indent=2)

    total = len(all_metadata)
    desktop = sum(1 for m in all_metadata.values() if m['category'] == 'desktop')
    mobile = sum(1 for m in all_metadata.values() if m['category'] == 'mobile')

    print(f'\n=== PROCESSING COMPLETE ===')
    print(f'Total: {total} images ({desktop} desktop, {mobile} mobile)')
    print(f'Metadata saved to {metadata_path}')


if __name__ == '__main__':
    main()
