$config = Get-Content "./config.json" | ConvertFrom-Json

foreach ($server in $config.servers) {
    if (Test-Path $server.txtPath) {
        Write-Host "[Processing] $($server.name)" -ForegroundColor Cyan
        if (!(Test-Path $server.dir)) { New-Item -ItemType Directory -Path $server.dir }
        
        $urls = Get-Content $server.txtPath
        foreach ($url in $urls) {
            $filename = Split-Path $url -Leaf
            $dest = Join-Path $server.dir $filename
            if (!(Test-Path $dest)) {
                try {
                    Invoke-WebRequest -Uri $url -OutFile $dest -ErrorAction Stop
                    Write-Host "DOWNLOADED: $filename"
                } catch {
                    Write-Host "ERROR: $url" -ForegroundColor Red
                }
            }
        }
    }
}
