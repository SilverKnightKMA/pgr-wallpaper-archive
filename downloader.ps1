$jobs = @(
    @{ path = "links_global.txt"; dir = "Wallpapers_Global" },
    @{ path = "links_cn.txt"; dir = "Wallpapers_CN" },
    @{ path = "links_jp.txt"; dir = "Wallpapers_JP" },
    @{ path = "links_kr.txt"; dir = "Wallpapers_KR" },
    @{ path = "links_tw.txt"; dir = "Wallpapers_TW" }
    
)

foreach ($job in $jobs) {
    if (Test-Path $job.path) {
        Write-Host "[Processing] $($job.path)"
        if (!(Test-Path $job.dir)) { New-Item -ItemType Directory -Path $job.dir }
        
        $urls = Get-Content $job.path
        foreach ($url in $urls) {
            $filename = split-path $url -leaf
            $dest = Join-Path $job.dir $filename
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
