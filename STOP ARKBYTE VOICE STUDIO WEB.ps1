$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Run = Join-Path $Root 'run'
foreach ($name in @('web.pid','backend.pid')) {
    $file = Join-Path $Run $name
    if (Test-Path $file) {
        $id = 0
        [void][int]::TryParse((Get-Content $file -Raw).Trim(), [ref]$id)
        if ($id -gt 0) {
            try { & taskkill.exe /PID $id /T /F 2>$null | Out-Null; Write-Host "Stopped process $id" } catch {}
        }
        Remove-Item $file -Force -ErrorAction SilentlyContinue
    }
}
Write-Host 'ArkByte Voice Studio Web stop command completed.' -ForegroundColor Green
