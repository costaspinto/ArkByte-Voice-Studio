$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root 'web'
$Service = Join-Path $Root 'service'
$Logs = Join-Path $Root 'logs'
Write-Host "`nARKBYTE VOICE STUDIO WEB — DIAGNOSTICS" -ForegroundColor Cyan
Write-Host "Project: $Root"
Write-Host "`n[Runtime checks]" -ForegroundColor Yellow
foreach ($cmd in @('node.exe','npm.cmd','py.exe','ffmpeg.exe','ffprobe.exe')) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) { Write-Host "$cmd : $($found.Source)" -ForegroundColor Green } else { Write-Host "$cmd : not found in PATH" -ForegroundColor Yellow }
}
$pythonFile = Join-Path $Root 'python-runtime.txt'
if (Test-Path $pythonFile) {
    $python = (Get-Content $pythonFile -Raw).Trim()
    Write-Host "`nPython runtime: $python"
    if (Test-Path $python) {
        & $python --version
        $backendProbe = Join-Path $Root 'verify_backend_preflight.py'
        if (Test-Path -LiteralPath $backendProbe) { & $python $backendProbe }
        else { Write-Host 'Backend probe script missing; reinstall from the verified package.' -ForegroundColor Red }
        $aiProbe = Join-Path $Root 'verify_ai_engine.py'
        if (Test-Path -LiteralPath $aiProbe) { & $python $aiProbe }
        else { Write-Host 'AI probe script missing; reinstall from the verified package.' -ForegroundColor Red }
    }
    else { Write-Host 'Configured Python runtime is missing.' -ForegroundColor Red }
} else { Write-Host 'python-runtime.txt is missing. Run INSTALL_WEB_WINDOWS.ps1.' -ForegroundColor Red }
Write-Host "`n[Project checks]" -ForegroundColor Yellow
foreach ($path in @((Join-Path $Web 'package.json'),(Join-Path $Web 'node_modules\next'),(Join-Path $Web '.env.local'),(Join-Path $Service 'main.py'))) {
    Write-Host "$(if (Test-Path $path) {'OK'} else {'MISSING'})  $path"
}
Write-Host "`n[Port checks]" -ForegroundColor Yellow
Get-NetTCPConnection -State Listen -LocalPort 3000,8765 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize
Write-Host "`n[Data checks]" -ForegroundColor Yellow
$data = Join-Path $env:LOCALAPPDATA 'ArkByte Voice Studio'
if (Test-Path $data) { Get-ChildItem $data -Force | Select-Object Name,Mode,LastWriteTime | Format-Table -AutoSize } else { Write-Host "Data directory not yet created: $data" }
Write-Host "`n[Recent logs]" -ForegroundColor Yellow
if (Test-Path $Logs) { Get-ChildItem $Logs -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,Length,LastWriteTime | Format-Table -AutoSize; foreach ($log in @('backend-error.log','nextjs-error.log')) { $p=Join-Path $Logs $log; if (Test-Path $p) { Write-Host "`n--- $log ---" -ForegroundColor Cyan; Get-Content $p -Tail 60 } } } else { Write-Host 'No local web logs yet.' }
Write-Host "`nDiagnostics finished. Share this output if setup or launch fails." -ForegroundColor Green
