$config = Get-Content "./config.json" | ConvertFrom-Json
Write-Host "=== PGR DOWNLOADER START ===" -ForegroundColor Yellow

foreach ($server in $config.servers) {
    Write-Host "`n--- Processing: $($server.name) ---" -ForegroundColor Cyan
    
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
        
        Write-Progress -Activity "Downloading from $($server.name)" -Status "File $count/$total: $filename" -PercentComplete (($count/$total)*100)

        if (!(Test-Path $dest)) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $dest -ErrorAction Stop
                Write-Host "  [$count/$total] DOWNLOADED: $filename" -ForegroundColor Green
                $downloaded++
            } catch {
                Write-Host "  [$count/$total] ERROR: $filename" -ForegroundColor Red
            }
        } else {
            # Log mờ cho các file đã tồn tại để tránh rác màn hình
            Write-Host "  [$count/$total] SKIPPED: $filename (Exists)" -ForegroundColor DarkGray
        }
    }
    Write-Host " >> Finish $($server.name): $downloaded new files added." -ForegroundColor Green
}
Write-Host "`n=== ALL DOWNLOADS FINISHED ===" -ForegroundColor Yellow
