# --- CONFIGURATION ---
$fileMapping = @{
    "links_global.txt" = "Wallpapers_Global"
    "links_cn.txt"     = "Wallpapers_CN"
}
$readmePath = "./README.md"
# ---------------------

$totalNew = 0
$totalSkipped = 0
$totalFailed = 0

foreach ($item in $fileMapping.GetEnumerator()) {
    $inputFile = $item.Key
    $outputDir = Join-Path "." $item.Value
    if (-not (Test-Path $inputFile)) { continue }
    if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Force -Path $outputDir | Out-Null }

    Write-Host "`n[Processing] $inputFile" -ForegroundColor Yellow
    $urls = Get-Content $inputFile
    foreach ($line in $urls) {
        $url = $line.Trim()
        if (-not $url) { continue }
        try {
            $rawName = $url.Split('/')[-1].Split('?')[0]
            $filename = [System.Uri]::UnescapeDataString($rawName) -replace '[\\/:*?"<>|]', '_'
            if ($filename.Length -gt 150) { $filename = $filename.Substring($filename.Length - 150) }
            $path = Join-Path $outputDir $filename

            if (-not (Test-Path $path)) {
                Write-Host "DOWNLOAD: $filename" -ForegroundColor Green
                Invoke-WebRequest -Uri $url -OutFile $path -ErrorAction Stop -TimeoutSec 60
                $totalNew++
            } else { $totalSkipped++ }
        } catch {
            Write-Host "ERROR: $url" -ForegroundColor Red
            $totalFailed++
        }
    }
}

# --- GENERATE GALLERY MARKDOWN ---
function Get-GalleryHtml($path) {
    if (-not (Test-Path $path)) { return "No images yet." }
    $images = Get-ChildItem -Path $path -File | Sort-Object LastWriteTime -Descending | Select-Object -First 6
    $html = "<table><tr>"
    $count = 0
    foreach ($img in $images) {
        if ($count -eq 3) { $html += "</tr><tr>" }
        $encodedName = [System.Web.HttpUtility]::UrlEncode($img.Name)
        $relPath = "$path/$encodedName"
        $html += "<td><img src='$relPath' width='250'><br><sub>$($img.Name)</sub></td>"
        $count++
    }
    $html += "</tr></table>"
    return $html
}

$globalGallery = Get-GalleryHtml "Wallpapers_Global"
$cnGallery = Get-GalleryHtml "Wallpapers_CN"

# --- UPDATE README ---
$globalCount = (Get-ChildItem -Path "./Wallpapers_Global" -File -ErrorAction SilentlyContinue).Count
$cnCount = (Get-ChildItem -Path "./Wallpapers_CN" -File -ErrorAction SilentlyContinue).Count
$lastUpdate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$newContent = @"
### 📊 Repository Statistics
- **Total Wallpapers:** $($globalCount + $cnCount)
  - 🌐 **Global Server:** $globalCount
  - 🇨🇳 **CN Server:** $cnCount
- **Last Sync:** $lastUpdate (UTC)
- **Last Result:** $totalNew added, $totalSkipped skipped.

### 🖼️ Latest Previews (Global)
$globalGallery

### 🖼️ Latest Previews (CN)
$cnGallery
"@

$readme = Get-Content $readmePath -Raw
$readme = $readme -replace "(?s)### 📊 Repository Statistics.*", $newContent
$readme | Set-Content $readmePath -Encoding UTF8

Write-Host "`n✅ Done! README updated with gallery." -ForegroundColor Cyan
