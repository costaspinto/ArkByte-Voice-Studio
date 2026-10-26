[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path)).TrimEnd('\')
$Web = Join-Path $Root 'web'
$Service = Join-Path $Root 'service'
$Logs = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$Transcript = Join-Path $Logs ("one-click-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$TestHome = Join-Path $env:TEMP ("ArkByte-Runner-Test-{0}" -f [Guid]::NewGuid().ToString('N'))
$oldPythonPath = $env:PYTHONPATH
$oldToken = $env:ARKBYTE_BRIDGE_TOKEN
$oldHome = $env:ARKBYTE_VOICE_HOME
$oldHFHome = $env:HF_HOME
$oldTorchHome = $env:TORCH_HOME
$oldTelemetry = $env:HF_HUB_DISABLE_TELEMETRY
$oldNextTelemetry = $env:NEXT_TELEMETRY_DISABLED
$transcriptStarted = $false

function Stop-WithMessage([string]$Message, [string]$Advice) {
    Write-Host "`nCHECK FAILED: $Message" -ForegroundColor Red
    Write-Host "Next step: $Advice" -ForegroundColor Yellow
    throw $Message
}
function Invoke-Checked([string]$File, [string[]]$Arguments, [string]$WorkingDirectory, [string]$Label) {
    Write-Host "`n== $Label ==" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $File @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
}
function Get-ListenerRows([int]$Port) {
    try { return @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) }
    catch { return @() }
}
function Get-ProcessById([int]$Id) {
    if ($Id -le 0) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $Id" -ErrorAction SilentlyContinue | Select-Object -First 1
}
function Test-ArkByteBackend($Process) {
    if ($null -eq $Process) { return $false }
    $name = [System.IO.Path]::GetFileName([string]$Process.ExecutablePath)
    $cmd = ([string]$Process.CommandLine).Replace('/','\')
    return (($name -ieq 'python.exe' -or $name -ieq 'pythonw.exe') -and
        $cmd.IndexOf($Service.Replace('/','\').TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd -match '(?i)uvicorn' -and $cmd -match '(?i)main:app' -and
        $cmd -match '(?i)--port\s+8765' -and $cmd -match '(?i)--app-dir')
}
function Test-ArkByteWeb($Process) {
    if ($null -eq $Process) { return $false }
    $name = [System.IO.Path]::GetFileName([string]$Process.ExecutablePath)
    $cmd = ([string]$Process.CommandLine).Replace('/','\')
    return ($name -ieq 'node.exe' -and
        $cmd.IndexOf($Web.Replace('/','\').TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf('next\dist\bin\next', [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd -match '(?i)\s(start|dev)(\s|$)' -and $cmd -match '(?i)--hostname\s+127\.0\.0\.1')
}
function Get-BridgeToken {
    $file = Join-Path $Web '.env.local'
    $line = Get-Content -LiteralPath $file | Where-Object { $_ -match '^ARKBYTE_BRIDGE_TOKEN=' } | Select-Object -First 1
    if (!$line) { throw 'ARKBYTE_BRIDGE_TOKEN is missing from web\.env.local.' }
    return $line.Substring('ARKBYTE_BRIDGE_TOKEN='.Length).Trim()
}

try {
    try { Start-Transcript -LiteralPath $Transcript -Force | Out-Null; $transcriptStarted = $true } catch { Write-Warning 'Transcript logging could not be started.' }
    Write-Host 'ARKBYTE VOICE STUDIO - ONE CLICK CHECK / BUILD / START' -ForegroundColor Green
    Write-Host "Project: $Root"

    $pythonFile = Join-Path $Root 'python-runtime.txt'
    if (!(Test-Path -LiteralPath $pythonFile)) { Stop-WithMessage 'python-runtime.txt was not found.' 'Create it with the full path to the existing CUDA Python executable.' }
    $Python = (Get-Content -LiteralPath $pythonFile -Raw).Trim()
    if (![System.IO.Path]::IsPathRooted($Python)) { $Python = Join-Path $Root $Python }
    $Python = [System.IO.Path]::GetFullPath($Python)
    if (!(Test-Path -LiteralPath $Python -PathType Leaf)) { Stop-WithMessage "Configured Python was not found: $Python" 'Correct python-runtime.txt. Do not delete or replace the CUDA environment.' }

    $pythonVersion = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    if ($LASTEXITCODE -ne 0 -or [Version]$pythonVersion -lt [Version]'3.10') { Stop-WithMessage "Unsupported Python runtime: $pythonVersion" 'Use the existing Python 3.12 CUDA environment.' }
    Write-Host "Python: $Python ($pythonVersion)" -ForegroundColor Green
    & $Python -c "import fastapi, uvicorn, numpy, torch; import chatterbox; print('Backend imports: OK'); print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage 'Core Python/AI imports failed.' 'Review the configured runtime. Do not reinstall or upgrade PyTorch automatically.' }
    Invoke-Checked -File $Python -Arguments @('-m','pip','check') -WorkingDirectory $Root -Label 'Python dependency consistency'

    $node = Get-Command node -ErrorAction SilentlyContinue
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (!$npmCommand) { $npmCommand = Get-Command npm -ErrorAction SilentlyContinue }
    if (!$node -or !$npmCommand) { Stop-WithMessage 'Node.js or npm is not on PATH.' 'Install the supported Node.js runtime, then reopen PowerShell.' }
    $nodeVersion = (& $node.Source -p 'process.versions.node').Trim()
    $npmVersion = (& $npmCommand.Source --version).Trim()
    if ([Version]$nodeVersion -lt [Version]'20.9.0' -or [Version]$npmVersion -lt [Version]'10.0.0') { Stop-WithMessage "Unsupported Node/npm versions: Node $nodeVersion, npm $npmVersion" 'Use Node 20.9+ and npm 10+.' }
    Write-Host "Node: $nodeVersion | npm: $npmVersion" -ForegroundColor Green
    if (!(Test-Path -LiteralPath (Join-Path $Web 'node_modules\next'))) { Stop-WithMessage 'Next.js dependencies are missing.' 'Run npm ci inside the web folder.' }
    if (!(Test-Path -LiteralPath (Join-Path $Web '.env.local'))) { Stop-WithMessage 'web\.env.local is missing.' 'Run INSTALL_WEB_WINDOWS.ps1 once to create the local bridge token.' }

    # If both ports are already served by healthy instances from this exact project, do not treat it as failure.
    $backendRows = @(Get-ListenerRows 8765)
    $webRows = @(Get-ListenerRows 3000)
    if ($backendRows.Count -gt 0 -or $webRows.Count -gt 0) {
        $backendProc = if ($backendRows.Count -eq 1) { Get-ProcessById ([int]$backendRows[0].OwningProcess) } else { $null }
        $webProc = if ($webRows.Count -eq 1) { Get-ProcessById ([int]$webRows[0].OwningProcess) } else { $null }
        if ($backendRows.Count -eq 1 -and $webRows.Count -eq 1 -and $backendRows[0].LocalAddress -eq '127.0.0.1' -and $webRows[0].LocalAddress -eq '127.0.0.1' -and (Test-ArkByteBackend $backendProc) -and (Test-ArkByteWeb $webProc)) {
            try {
                $headers = @{ 'X-ArkByte-Token' = (Get-BridgeToken) }
                $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health' -Headers $headers -TimeoutSec 4
                $null = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 4 -UseBasicParsing
                Write-Host "`nARKBYTE IS ALREADY RUNNING AND HEALTHY. No duplicate start was attempted." -ForegroundColor Green
                Write-Host 'Open: http://127.0.0.1:3000'
                Start-Process 'http://127.0.0.1:3000'
                return
            } catch { Stop-WithMessage "The existing ArkByte listeners match this project, but health checks failed: $($_.Exception.Message)" 'Review logs\backend-error.log and logs\nextjs-error.log. Run the Stop command, then start again.' }
        }
        $details = @()
        foreach ($row in $backendRows) { $details += "port 8765 PID $($row.OwningProcess)" }
        foreach ($row in $webRows) { $details += "port 3000 PID $($row.OwningProcess)" }
        Stop-WithMessage ("Application port(s) are occupied: " + ($details -join '; ')) 'No process was changed. Use STOP ARKBYTE VOICE STUDIO WEB.cmd for a verified ArkByte session, or investigate the unrelated listener.'
    }

    if (!$SkipTests) {
        $env:PYTHONPATH = $Service
        $env:ARKBYTE_BRIDGE_TOKEN = 'arkbyte-test-only-' + [Guid]::NewGuid().ToString('N')
        $env:ARKBYTE_VOICE_HOME = $TestHome
        New-Item -ItemType Directory -Force -Path $TestHome | Out-Null
        Invoke-Checked -File $Python -Arguments @('-m','unittest','discover','-s',(Join-Path $Service 'tests'),'-p','test_*.py','-v') -WorkingDirectory $Service -Label 'Backend unit and API tests'
    } else { Write-Warning 'Backend tests skipped by request.' }

    if (!$SkipBuild) {
        Invoke-Checked -File $npmCommand.Source -Arguments @('run','check') -WorkingDirectory $Web -Label 'Frontend TypeScript check and production build'
    } else { Write-Warning 'Frontend typecheck/build skipped by request.' }
    if (!(Test-Path -LiteralPath (Join-Path $Web '.next\BUILD_ID'))) { Stop-WithMessage 'Production build output is missing.' 'Run this runner without -SkipBuild.' }

    $start = Join-Path $Root 'START ARKBYTE VOICE STUDIO WEB.ps1'
    if (!(Test-Path -LiteralPath $start)) { Stop-WithMessage 'The project startup script is missing.' 'Restore START ARKBYTE VOICE STUDIO WEB.ps1.' }
    Write-Host "`n== Launching ArkByte ==" -ForegroundColor Cyan
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    & $powershell -NoProfile -ExecutionPolicy Bypass -File $start -Production
    if ($LASTEXITCODE -ne 0) { throw "Application startup failed with exit code $LASTEXITCODE. Review logs in $Logs." }
    Write-Host "`nARKBYTE STARTUP SCRIPT REPORTED SUCCESS." -ForegroundColor Green
    Write-Host 'Open: http://127.0.0.1:3000'
    Write-Host "Runner log: $Transcript"
} catch {
    Write-Host "`nONE-CLICK RUNNER FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Logs: $Logs" -ForegroundColor Yellow
    exit 1
} finally {
    if ($TestHome -and (Test-Path -LiteralPath $TestHome)) { Remove-Item -LiteralPath $TestHome -Recurse -Force -ErrorAction SilentlyContinue }
    $env:PYTHONPATH = $oldPythonPath
    $env:ARKBYTE_BRIDGE_TOKEN = $oldToken
    $env:ARKBYTE_VOICE_HOME = $oldHome
    $env:HF_HOME = $oldHFHome
    $env:TORCH_HOME = $oldTorchHome
    $env:HF_HUB_DISABLE_TELEMETRY = $oldTelemetry
    $env:NEXT_TELEMETRY_DISABLED = $oldNextTelemetry
    if ($transcriptStarted) { try { Stop-Transcript | Out-Null } catch {} }
}
