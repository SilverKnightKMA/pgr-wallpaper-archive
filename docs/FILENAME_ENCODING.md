# Filename Encoding Strategy

## Overview

This document explains how filenames with special characters (Chinese, Japanese, Korean, etc.) are handled throughout the PGR Wallpaper Archive system.

## Core Principle

**Storage**: Files are stored with **decoded/unencoded names** (actual Unicode characters)  
**URLs**: Filenames in URLs are **percent-encoded** for web compatibility

## Example Flow

1. **Source URL from Scraper**:
   ```
   https://example.com/wallpaper-1234英文.jpg
   OR
   https://example.com/wallpaper-1234%E8%8B%B1%E6%96%87.jpg
   ```

2. **Downloaded File** (saved by downloader.ps1):
   ```
   wallpaper-1234英文.jpg  ← Always decoded
   ```

3. **Stored in Git Branches**:
   - Wallpapers branch: `wallpaper-1234英文.jpg`
   - Preview branch: `global/thumbnails/wallpaper-1234英文.jpg`

4. **Manifest Entry** (data/manifest.json):
   ```json
   {
     "filename": "wallpaper-1234英文.jpg"
   }
   ```

5. **URLs in README/Website**:
   ```
   https://github.com/.../raw/wallpapers/wallpaper-1234%E8%8B%B1%E6%96%87.jpg
   ```

## Implementation Details

### Downloader (src/downloader.ps1)

```powershell
# Lines 54-59
$filename = [System.IO.Path]::GetFileName($url)
$decodedFilename = [System.Uri]::UnescapeDataString($filename)
if ($decodedFilename -ne $filename) {
    $filename = $decodedFilename
}
```

**Purpose**: Ensures all files are saved with decoded names, regardless of whether the source URL was encoded or not.

### Manifest Builder (src/build_manifest.py)

```python
# Line 141
decoded_fn = urllib.parse.unquote(raw_fn)
fn = decoded_fn if decoded_fn != raw_fn else raw_fn
```

**Purpose**: Stores decoded filenames in manifest for consistency.

### README Generator (src/generate_readme.js)

```javascript
// Lines 22-27
function encodeFilename(filename) {
    return filename
        .replace(/[^A-Za-z0-9._~:@!$&'()*+,;=%\/-]/g, c => encodeURIComponent(c))
        .replace(/%(?![0-9A-Fa-f]{2})/g, '%25');
}
```

**Purpose**: Encodes filenames for use in URLs. This function is:
- **Idempotent**: Encoding an already-encoded filename doesn't double-encode it
- **Safe**: Preserves valid percent-encodings (e.g., `%20`)
- **Complete**: Encodes all non-URL-safe characters including Unicode

### Website (docs/index.html)

Uses the same `encodeFilename()` function for consistency.

## Why This Approach?

1. **Human-Readable**: Files in Git have readable names (e.g., `英文.jpg` not `%E8%8B%B1%E6%96%87.jpg`)
2. **Git-Friendly**: Git handles Unicode filenames natively
3. **Web-Compatible**: URLs are properly percent-encoded
4. **Robust**: Works whether source URLs are pre-encoded or not
5. **Idempotent**: Re-running encoding is safe

## Testing

Run the test suite to validate encoding behavior:

```bash
node tests/test_filename_encoding.js
```

The test suite validates:
- Chinese, Japanese, Korean character encoding
- Idempotency (no double-encoding)
- Special character handling
- Space encoding
- Percent sign handling
- Manifest consistency

## Troubleshooting

### Issue: Download links return 404

**Cause**: Mismatch between stored filename and URL encoding  
**Check**: 
1. Verify files in branches have decoded names: `git ls-tree wallpapers:`
2. Verify manifest has decoded names: Check `data/manifest.json`
3. Verify URLs use encoded names: Check README or website HTML

**Fix**: Ensure `encodeFilename()` is used consistently in all places that generate URLs.

### Issue: Filenames with % symbols cause problems

**Cause**: Lone `%` without valid hex digits  
**Solution**: The `encodeFilename()` function automatically encodes lone `%` to `%25`

## Related Files

- `src/downloader.ps1` - Downloads and decodes filenames
- `src/build_manifest.py` - Builds manifest with decoded filenames
- `src/generate_readme.js` - Generates READMEs with encoded URLs
- `docs/index.html` - Website with encoded URLs
- `.github/workflows/downloader.yml` - Workflow that coordinates everything
- `tests/test_filename_encoding.js` - Test suite

## Standards Compliance

- **RFC 3986** (URI): Follows percent-encoding rules
- **UTF-8**: All filenames stored as UTF-8
- **Git**: Uses Git's native Unicode filename support
