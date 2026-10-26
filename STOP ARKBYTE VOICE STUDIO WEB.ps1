[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference = 'Stop'
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path)).TrimEnd('\')
$Web = Join-Path $Root 'web'
$Service = Join-Path $Root 'service'
$Run = Join-Path $Root 'run'

function Get-ListenerRows([int]$Port) {
    try {
        return @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    } catch { return @() }
}
function Get-ProcessById([int]$Id) {
    if ($Id -le 0) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $Id" -ErrorAction SilentlyContinue | Select-Object -First 1
}
function Test-ArkByteBackend($Process) {
    if ($null -eq $Process) { return $false }
    $name = [System.IO.Path]::GetFileName([string]$Process.ExecutablePath)
    $cmd = ([string]$Process.CommandLine).Replace('/','\')
    $needle = $Service.Replace('/','\').TrimEnd('\')
    return (($name -ieq 'python.exe' -or $name -ieq 'pythonw.exe') -and
        $cmd.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd -match '(?i)uvicorn' -and $cmd -match '(?i)main:app' -and
        $cmd -match '(?i)--port\s+8765' -and $cmd -match '(?i)--app-dir')
}
function Test-ArkByteWeb($Process) {
    if ($null -eq $Process) { return $false }
    $name = [System.IO.Path]::GetFileName([string]$Process.ExecutablePath)
    $cmd = ([string]$Process.CommandLine).Replace('/','\')
    $needle = $Web.Replace('/','\').TrimEnd('\')
    return ($name -ieq 'node.exe' -and
        $cmd.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf('next\dist\bin\next', [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd -match '(?i)\s(start|dev)(\s|$)' -and
        $cmd -match '(?i)--hostname\s+127\.0\.0\.1')
}
function Get-VerifiedProjectListener([int]$Port, [string]$Kind) {
    $rows = @(Get-ListenerRows $Port)
    foreach ($row in $rows) {
        $proc = Get-ProcessById ([int]$row.OwningProcess)
        $valid = ($row.LocalAddress -eq '127.0.0.1') -and $(if ($Kind -eq 'backend') { Test-ArkByteBackend $proc } else { Test-ArkByteWeb $proc })
        if ($valid) {
            return [pscustomobject]@{ Port=$Port; PID=[int]$row.OwningProcess; Process=$proc; Kind=$Kind }
        }
    }
    return $null
}
function Stop-VerifiedListener($Target) {
    # Re-read both the listener and process immediately before termination to guard against PID reuse.
    $liveRows = @(Get-ListenerRows ([int]$Target.Port) | Where-Object { $_.LocalAddress -eq '127.0.0.1' -and [int]$_.OwningProcess -eq [int]$Target.PID })
    if ($liveRows.Count -eq 0) { Write-Host "$($Target.Kind) listener has already closed."; return }
    $fresh = Get-ProcessById ([int]$Target.PID)
    $valid = if ($Target.Kind -eq 'backend') { Test-ArkByteBackend $fresh } else { Test-ArkByteWeb $fresh }
    if (!$valid) { throw "Safety recheck failed for $($Target.Kind) PID $($Target.PID); process was not stopped." }
    Write-Host "Stopping verified ArkByte $($Target.Kind) listener PID $($Target.PID) on port $($Target.Port)..." -ForegroundColor Yellow
    & taskkill.exe /PID ([int]$Target.PID) /T /F
    if ($LASTEXITCODE -ne 0) { throw "taskkill failed for verified $($Target.Kind) PID $($Target.PID) (exit $LASTEXITCODE)." }
}

if (!(Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
    Write-Error 'Get-NetTCPConnection is unavailable. This Stop script requires Windows networking cmdlets.'
    exit 1
}
$backend = Get-VerifiedProjectListener 8765 'backend'
$frontend = Get-VerifiedProjectListener 3000 'web'
$unknown = @()
foreach ($port in @(8765,3000)) {
    foreach ($row in @(Get-ListenerRows $port)) {
        $known = ($row.LocalAddress -eq '127.0.0.1') -and ((($port -eq 8765) -and $backend -and ([int]$backend.PID -eq [int]$row.OwningProcess)) -or
                 (($port -eq 3000) -and $frontend -and ([int]$frontend.PID -eq [int]$row.OwningProcess)))
        if (!$known) { $unknown += [pscustomobject]@{ Port=$port; PID=[int]$row.OwningProcess } }
    }
}

if (!$backend -and !$frontend) {
    if ($unknown.Count -gt 0) {
        foreach ($item in $unknown) { Write-Warning "Port $($item.Port) is occupied by PID $($item.PID), which does not match this ArkByte project. It was NOT stopped." }
        Write-Warning 'No verified ArkByte listener was found. No process was stopped and run metadata was retained.'
        exit 1
    }
    Remove-Item -LiteralPath (Join-Path $Run 'ownership.json') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Run 'backend.pid') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Run 'web.pid') -Force -ErrorAction SilentlyContinue
    Write-Host 'ArkByte is already stopped. Stale run metadata has been cleared.' -ForegroundColor Green
    exit 0
}

Write-Host "Verified project: $Root" -ForegroundColor Cyan
if ($backend) { Write-Host "Backend: PID $($backend.PID), port 8765 — verified" -ForegroundColor Green }
if ($frontend) { Write-Host "Frontend: PID $($frontend.PID), port 3000 — verified" -ForegroundColor Green }
foreach ($item in $unknown) { Write-Warning "Port $($item.Port) also has unverified PID $($item.PID); it will be left untouched." }

if (!$Force) {
    $confirmation = Read-Host 'Type STOP ARKBYTE to stop only the verified ArkByte listeners'
    if ($confirmation -cne 'STOP ARKBYTE') {
        Write-Host 'Cancelled. No processes were stopped.' -ForegroundColor Yellow
        exit 0
    }
}

$stopErrors = @()
foreach ($target in @($frontend,$backend)) {
    if ($null -ne $target) {
        try { Stop-VerifiedListener $target } catch { $stopErrors += $_.Exception.Message; Write-Warning $_.Exception.Message }
    }
}

$deadline = (Get-Date).AddSeconds(12)
do {
    Start-Sleep -Milliseconds 500
    $stillBackend = Get-VerifiedProjectListener 8765 'backend'
    $stillFrontend = Get-VerifiedProjectListener 3000 'web'
} while (($stillBackend -or $stillFrontend) -and (Get-Date) -lt $deadline)

if (!$stillBackend -and !$stillFrontend) {
    Remove-Item -LiteralPath (Join-Path $Run 'ownership.json') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Run 'backend.pid') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Run 'web.pid') -Force -ErrorAction SilentlyContinue
    if ($stopErrors.Count -eq 0) {
        Write-Host 'ArkByte Voice Studio has stopped. Both project listeners are confirmed closed.' -ForegroundColor Green
        exit 0
    }
}

if ($stillBackend) { Write-Warning "Backend still listening on port 8765 (PID $($stillBackend.PID))." }
if ($stillFrontend) { Write-Warning "Frontend still listening on port 3000 (PID $($stillFrontend.PID))." }
Write-Warning 'ArkByte did not fully stop. Ownership metadata was retained for diagnosis.'
exit 1
