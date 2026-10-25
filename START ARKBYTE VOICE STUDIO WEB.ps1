[CmdletBinding()]
param([switch]$Production)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root 'web'
$Service = Join-Path $Root 'service'
$Run = Join-Path $Root 'run'
$Logs = Join-Path $Root 'logs'
$backend = $null
$next = $null
New-Item -ItemType Directory -Force -Path $Run,$Logs | Out-Null

function Fail([string]$Message, [string]$Advice) {
    Write-Host "`nSTARTUP FAILED: $Message" -ForegroundColor Red
    Write-Host "What to do: $Advice" -ForegroundColor Yellow
    Write-Host "Logs: $Logs" -ForegroundColor Gray
    throw $Message
}

try {
    $pythonFile = Join-Path $Root 'python-runtime.txt'
    if (!(Test-Path $pythonFile)) { Fail 'Python runtime path is not configured.' 'Run INSTALL_WEB_WINDOWS.ps1 first.' }
    $Python = (Get-Content $pythonFile -Raw).Trim()
    if (!(Test-Path -LiteralPath $Python -PathType Leaf)) { Fail 'Configured Python executable is missing.' 'Run INSTALL_WEB_WINDOWS.ps1 to repair the runtime.' }
    if (!(Test-Path (Join-Path $Web 'node_modules\next'))) { Fail 'Next.js dependencies are missing.' 'Run INSTALL_WEB_WINDOWS.ps1.' }
    $envFile = Join-Path $Web '.env.local'
    if (!(Test-Path $envFile)) { Fail 'Local bridge credentials are missing.' 'Run INSTALL_WEB_WINDOWS.ps1 to generate a local token.' }
    $tokenLine = Get-Content $envFile | Where-Object { $_ -match '^ARKBYTE_BRIDGE_TOKEN=' } | Select-Object -First 1
    if (!$tokenLine) { Fail 'Local bridge token is missing.' 'Rerun INSTALL_WEB_WINDOWS.ps1.' }
    $env:ARKBYTE_BRIDGE_TOKEN = $tokenLine.Substring('ARKBYTE_BRIDGE_TOKEN='.Length).Trim()
    $env:ARKBYTE_BRIDGE_URL = 'http://127.0.0.1:8765'
    $env:ARKBYTE_VOICE_HOME = Join-Path $env:LOCALAPPDATA 'ArkByte Voice Studio'
    $env:HF_HOME = Join-Path $env:ARKBYTE_VOICE_HOME 'cache\huggingface'
    $env:TORCH_HOME = Join-Path $env:ARKBYTE_VOICE_HOME 'cache\torch'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    New-Item -ItemType Directory -Force -Path $env:ARKBYTE_VOICE_HOME,$env:HF_HOME,$env:TORCH_HOME | Out-Null
    $env:PYTHONPATH = $Service
    $env:NEXT_TELEMETRY_DISABLED = '1'

    $busyPorts = @(Get-NetTCPConnection -State Listen -LocalPort 8765,3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort -Unique)
    if ($busyPorts.Count -gt 0) {
        $details = ($busyPorts -join ', ')
        throw "Port(s) $details are already in use. Run STOP ARKBYTE VOICE STUDIO WEB.cmd or close the application using those ports, then retry."
    }
    if ($Production -and !(Test-Path (Join-Path $Web '.next\BUILD_ID'))) {
        throw 'The production web build was not found. Run BUILD ARKBYTE VOICE STUDIO WEB.cmd before starting with -Production.'
    }

    $backendOut = Join-Path $Logs 'backend.log'
    $webOut = Join-Path $Logs 'nextjs.log'
    $backendErr = Join-Path $Logs 'backend-error.log'
    $webErr = Join-Path $Logs 'nextjs-error.log'
    Write-Host 'Starting local Python voice service…' -ForegroundColor Cyan
    $backendArgs = "-m uvicorn main:app --app-dir `"$Service`" --host 127.0.0.1 --port 8765 --no-access-log"
    $backend = Start-Process -FilePath $Python -ArgumentList $backendArgs -WorkingDirectory $Service -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
    Set-Content -LiteralPath (Join-Path $Run 'backend.pid') -Value $backend.Id

    Write-Host 'Starting Next.js web application…' -ForegroundColor Cyan
    $cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'
    $npmCommand = if ($Production) { 'npm run start' } else { 'npm run dev' }
    $next = Start-Process -FilePath $cmd -ArgumentList @('/d','/s','/c',$npmCommand) -WorkingDirectory $Web -PassThru -WindowStyle Hidden -RedirectStandardOutput $webOut -RedirectStandardError $webErr
    Set-Content -LiteralPath (Join-Path $Run 'web.pid') -Value $next.Id

    Write-Host 'Waiting for local services…' -ForegroundColor Yellow
    $backendReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (!$backend.HasExited) {
            try {
                $headers = @{ 'X-ArkByte-Token' = $env:ARKBYTE_BRIDGE_TOKEN }
                $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health' -Headers $headers -TimeoutSec 2
                $backendReady = $true; break
            } catch { Start-Sleep -Seconds 1 }
        } else { break }
    }
    if (!$backendReady) {
        $tail = if (Test-Path $backendErr) { (Get-Content $backendErr -Tail 30 | Out-String) } else { 'No backend stderr log was created.' }
        Fail "Python service did not become ready. $tail" 'Check backend-error.log. Confirm Python dependencies, local port 8765 and the Python runtime path. Run INSTALL_WEB_WINDOWS.ps1 again if needed.'
    }
    $webReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 2 -UseBasicParsing; $webReady = $true; break } catch { Start-Sleep -Seconds 1 }
    }
    if (!$webReady) {
        $tail = if (Test-Path $webErr) { (Get-Content $webErr -Tail 30 | Out-String) } else { 'No Next.js stderr log was created.' }
        Fail "Next.js did not become ready. $tail" 'Check nextjs-error.log. Run npm install from the web folder, then rerun setup.'
    }
    Write-Host "`nARKBYTE VOICE STUDIO WEB IS READY" -ForegroundColor Green
    Write-Host "Mode: $(if ($Production) { 'Production' } else { 'Development' })"
    Write-Host 'Open: http://127.0.0.1:3000'
    Write-Host "Backend log: $backendOut"
    Write-Host "Frontend log: $webOut"
    Start-Process 'http://127.0.0.1:3000'
}
catch {
    Write-Host "`nStartup failed. Cleaning up any service started by this launch attempt..." -ForegroundColor Yellow
    foreach ($process in @($next, $backend)) {
        if ($null -ne $process) {
            try {
                $process.Refresh()
                if (!$process.HasExited) {
                    & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
                }
            } catch { Write-Warning "Could not automatically stop process $($process.Id): $($_.Exception.Message)" }
        }
    }
    foreach ($pidFile in @('web.pid', 'backend.pid')) {
        Remove-Item -LiteralPath (Join-Path $Run $pidFile) -Force -ErrorAction SilentlyContinue
    }
    if ($_.Exception.Message -notlike 'STARTUP FAILED:*') { Write-Host "`nUnexpected startup error: $($_.Exception.Message)" -ForegroundColor Red }
    Write-Host "Review logs in: $Logs" -ForegroundColor Yellow
    exit 1
}
