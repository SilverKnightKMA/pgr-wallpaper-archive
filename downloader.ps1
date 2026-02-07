# --- CONFIGURATION ---
$fileMapping = @{
    "links_global.txt" = "Wallpapers_Global"
    "links_cn.txt"     = "Wallpapers_CN"
}
# ---------------------

$totalNew = 0
$totalSkipped = 0
$totalFailed = 0

foreach ($item in $fileMapping.GetEnumerator()) {
    $inputFile = $item.Key
    $outputDir = Join-Path "." $item.Value
    
    if (-not (Test-Path $inputFile)) { continue }
    if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Force -Path $outputDir | Out-Null }

    Write-Host "`n[Processing] $inputFile -> $outputDir" -ForegroundColor Yellow
    
    $urls = Get-Content $inputFile
    foreach ($line in $urls) {
        $url = $line.Trim()
        if (-not $url) { continue }
        
        try {
            $rawName = $url.Split('/')[-1].Split('?')[0]
            $filename = [System.Uri]::UnescapeDataString($rawName)
            $filename = $filename -replace '[\\/:*?"<>|]', '_'
            
            if ($filename.Length -gt 150) { $filename = $filename.Substring($filename.Length - 150) }
            $path = Join-Path $outputDir $filename

            if (-not (Test-Path $path)) {
                Write-Host "Downloading: $filename" -ForegroundColor Green
                Invoke-WebRequest -Uri $url -OutFile $path -ErrorAction Stop -TimeoutSec 60
                $totalNew++
            } else {
                $totalSkipped++
            }
        } catch {
            Write-Host "Error: Failed to download $url" -ForegroundColor Red
            $totalFailed++
        }
    }
}

# --- UPDATE README STATISTICS ---
$globalCount = (Get-ChildItem -Path "./Wallpapers_Global" -File -ErrorAction SilentlyContinue).Count
$cnCount = (Get-ChildItem -Path "./Wallpapers_CN" -File -ErrorAction SilentlyContinue).Count
$grandTotal = $globalCount + $cnCount
$lastUpdate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$statsBlock = @"
### 📊 Repository Statistics
- **Total Wallpapers:** $grandTotal
  - 🌐 **Global Server:** $globalCount
  - 🇨🇳 **CN Server:** $cnCount
- **Last Updated:** $lastUpdate (UTC)
- **Last Action Result:** $totalNew added, $totalSkipped skipped, $totalFailed failed.
"@

$readmePath = "./README.md"
if (Test-Path $readmePath) {
    $content = Get-Content $readmePath -Raw
    # Replace the old stats section with new data
    $content = $content -replace "(?s)### 📊 Repository Statistics.*", $statsBlock
    $content | Set-Content $readmePath -Encoding UTF8
}

Write-Host "`n✅ All tasks finished. Statistics updated." -ForegroundColor Cyan
