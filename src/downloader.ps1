$configPath = Join-Path $PSScriptRoot ".." "config.json"
$configPath = [System.IO.Path]::GetFullPath($configPath)

if (!(Test-Path $configPath)) {
    Write-Host "Config not found: $configPath" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath | ConvertFrom-Json

Write-Host "=== PGR DOWNLOADER START ===" -ForegroundColor Yellow

foreach ($server in $config.servers) {
    $serverName = $server.name
    $serverId   = $server.id
    $txtPath    = $server.txtPath

    # Download to per-server branch directory
    $serverDir = Join-Path $PSScriptRoot ".." "branches" $serverId
    $serverDir = [System.IO.Path]::GetFullPath($serverDir)

    Write-Host "`n--- Processing: $serverName ---" -ForegroundColor Cyan
    Write-Host " [i] Reading links from: $txtPath" -ForegroundColor DarkGray

    if (!(Test-Path $txtPath)) {
        Write-Host " [!] Skip: File $txtPath not found." -ForegroundColor Yellow
        continue
    }

    if (!(Test-Path $serverDir)) {
        New-Item -ItemType Directory -Path $serverDir | Out-Null
        Write-Host " [+] Created folder: $serverDir" -ForegroundColor Gray
    }

    $urls = Get-Content $txtPath
    $total = $urls.Count

    # Thread-safe counters
    $countRef      = [ref] 0
    $downloadedRef = [ref] 0

    # Multi-threaded download
    $urls | ForEach-Object -Parallel {
        $url      = $_
        $dir      = $using:serverDir
        $tot      = $using:total
        $cntRef   = $using:countRef
        $dlRef    = $using:downloadedRef

        $filename = [System.IO.Path]::GetFileName($url)
        $dest     = Join-Path $dir $filename
        $idx      = [System.Threading.Interlocked]::Increment($cntRef)

        if (!(Test-Path $dest)) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $dest -ErrorAction Stop
                [System.Threading.Interlocked]::Increment($dlRef) | Out-Null
                Write-Host "  [$idx/$tot] DOWNLOADED: $filename" -ForegroundColor Green
            } catch {
                Write-Host "  [$idx/$tot] ERROR: $filename - $_" -ForegroundColor Red
            }
        } else {
            Write-Host "  [$idx/$tot] SKIPPED: $filename (Exists)" -ForegroundColor DarkGray
        }
    } -ThrottleLimit 16

    Write-Host " >> Finish $serverName : $($downloadedRef.Value) new files added." -ForegroundColor Green
}
Write-Host "`n=== ALL DOWNLOADS FINISHED ===" -ForegroundColor Yellow
