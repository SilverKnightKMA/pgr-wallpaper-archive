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

    # Multi-threaded download using ForEach-Object -Parallel
    $urls | ForEach-Object -Parallel {
        $url = $_
        $filename = [System.IO.Path]::GetFileName($url)
        $dest = Join-Path $using:server.dir $filename

        if (!(Test-Path $dest)) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $dest -ErrorAction Stop
                Write-Host "  [$(++$using:count)/$using:total] DOWNLOADED: $filename" -ForegroundColor Green
                $using:downloaded++
            } catch {
                Write-Host "  [$(++$using:count)/$using:total] ERROR: $filename" -ForegroundColor Red
            }
        } else {
            Write-Host "  [$(++$using:count)/$using:total] SKIPPED: $filename (Exists)" -ForegroundColor DarkGray
        }
    } -ThrottleLimit 16 # Limit to 8 parallel downloads

    Write-Host " >> Finish $($server.name): $downloaded new files added." -ForegroundColor Green
}
Write-Host "`n=== ALL DOWNLOADS FINISHED ===" -ForegroundColor Yellow
