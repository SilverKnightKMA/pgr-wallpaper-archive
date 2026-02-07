$configPath = Join-Path $PSScriptRoot ".." "config.json"
$configPath = [System.IO.Path]::GetFullPath($configPath)

if (!(Test-Path $configPath)) {
    Write-Host "❌ Config not found: $configPath" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath | ConvertFrom-Json

Write-Host "=== PGR DOWNLOADER START ===" -ForegroundColor Yellow

foreach ($server in $config.servers) {
    Write-Host "`n--- Processing: $($server.name) ---" -ForegroundColor Cyan
    Write-Host " [i] Reading links from: $($server.txtPath)" -ForegroundColor DarkGray
    
    if (!(Test-Path $server.txtPath)) {
        Write-Host " [!] Skip: File $($server.txtPath) not found." -ForegroundColor Yellow
        continue
    }

    if (!(Test-Path $server.dir)) { 
        New-Item -ItemType Directory -Path $server.dir | Out-Null
        Write-Host " [+] Created folder: $($server.dir)" -ForegroundColor Gray
    }

    $urls = Get-Content $server.txtPath
    $total = $urls.Count
    $count = 0
    $downloaded = 0

    foreach ($url in $urls) {
        $count++
        $filename = Split-Path $url -Leaf
        $dest = Join-Path $server.dir $filename
        
        if (!$env:GITHUB_ACTIONS) {
            Write-Progress -Activity "Downloading from $($server.name)" -Status "File $count/${total}: $filename" -PercentComplete (($count/$total)*100)
        }

        if (!(Test-Path $dest)) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $dest -ErrorAction Stop
                Write-Host "  [$count/${total}] DOWNLOADED: $filename" -ForegroundColor Green
                $downloaded++
            } catch {
                Write-Host "  [$count/${total}] ERROR: $filename" -ForegroundColor Red
            }
        } else {
            Write-Host "  [$count/${total}] SKIPPED: $filename (Exists)" -ForegroundColor DarkGray
        }
    }
    Write-Host " >> Finish $($server.name): $downloaded new files added." -ForegroundColor Green
}
Write-Host "`n=== ALL DOWNLOADS FINISHED ===" -ForegroundColor Yellow
