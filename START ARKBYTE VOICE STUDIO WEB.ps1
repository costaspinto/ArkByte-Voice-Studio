[CmdletBinding()]
param([switch]$Production)
$ErrorActionPreference = 'Stop'
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path)).TrimEnd('\')
$Web = Join-Path $Root 'web'
$Service = Join-Path $Root 'service'
$Run = Join-Path $Root 'run'
$Logs = Join-Path $Root 'logs'
$backend = $null
$nextLauncher = $null
$backendPid = 0
$webPid = 0
New-Item -ItemType Directory -Force -Path $Run,$Logs | Out-Null

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
    $serviceNeedle = $Service.Replace('/','\').TrimEnd('\')
    return (($name -ieq 'python.exe' -or $name -ieq 'pythonw.exe') -and
        $cmd.IndexOf($serviceNeedle, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd -match '(?i)uvicorn' -and $cmd -match '(?i)main:app' -and
        $cmd -match '(?i)--port\s+8765' -and $cmd -match '(?i)--app-dir')
}
function Test-ArkByteWeb($Process) {
    if ($null -eq $Process) { return $false }
    $name = [System.IO.Path]::GetFileName([string]$Process.ExecutablePath)
    $cmd = ([string]$Process.CommandLine).Replace('/','\')
    $webNeedle = $Web.Replace('/','\').TrimEnd('\')
    return ($name -ieq 'node.exe' -and
        $cmd.IndexOf($webNeedle, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd.IndexOf('next\dist\bin\next', [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $cmd -match '(?i)\s(start|dev)(\s|$)' -and
        $cmd -match '(?i)--hostname\s+127\.0\.0\.1')
}
function Get-BridgeToken {
    $file = Join-Path $Web '.env.local'
    if (!(Test-Path -LiteralPath $file)) { throw 'web\.env.local is missing.' }
    $line = Get-Content -LiteralPath $file | Where-Object { $_ -match '^ARKBYTE_BRIDGE_TOKEN=' } | Select-Object -First 1
    if (!$line) { throw 'ARKBYTE_BRIDGE_TOKEN is missing from web\.env.local.' }
    $value = $line.Substring('ARKBYTE_BRIDGE_TOKEN='.Length).Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($value) -or $value -match '^(?i)(change[-_ ]?me|your[-_ ]?token|replace[-_ ]?me|placeholder)$') {
        throw 'ARKBYTE_BRIDGE_TOKEN is empty or still a placeholder in web\\.env.local.'
    }
    if ($value.Length -lt 32) {
        throw 'ARKBYTE_BRIDGE_TOKEN is too short. Generate a random token of at least 32 characters in web\\.env.local.'
    }
    return $value
}
function Write-Ownership([int]$BackendId, [int]$WebId, [string]$PythonPath, [string]$WebCommand, [string]$StartedUtc) {
    $record = [ordered]@{
        schema = 2
        root = $Root
        started_utc = $StartedUtc
        backend_pid = $BackendId
        backend_executable = $PythonPath
        backend_service = $Service
        backend_port = 8765
        web_pid = $WebId
        web_command = $WebCommand
        web_directory = $Web
        web_port = 3000
    }
    $temp = Join-Path $Run 'ownership.json.tmp'
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination (Join-Path $Run 'ownership.json') -Force
    Set-Content -LiteralPath (Join-Path $Run 'backend.pid') -Value $BackendId -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $Run 'web.pid') -Value $WebId -Encoding ASCII
}
function Fail([string]$Message, [string]$Advice) {
    Write-Host "`nSTARTUP FAILED: $Message" -ForegroundColor Red
    Write-Host "What to do: $Advice" -ForegroundColor Yellow
    Write-Host "Logs: $Logs" -ForegroundColor Gray
    throw $Message
}

try {
    $pythonFile = Join-Path $Root 'python-runtime.txt'
    if (!(Test-Path -LiteralPath $pythonFile)) { Fail 'Python runtime path is not configured.' 'Run INSTALL_WEB_WINDOWS.ps1 first.' }
    $Python = (Get-Content -LiteralPath $pythonFile -Raw).Trim()
    if (![System.IO.Path]::IsPathRooted($Python)) { $Python = Join-Path $Root $Python }
    $Python = [System.IO.Path]::GetFullPath($Python)
    if (!(Test-Path -LiteralPath $Python -PathType Leaf)) { Fail 'Configured Python executable is missing.' 'Check python-runtime.txt. Do not recreate or replace the CUDA environment automatically.' }
    if (!(Test-Path -LiteralPath (Join-Path $Web 'node_modules\next'))) { Fail 'Next.js dependencies are missing.' 'Run INSTALL_WEB_WINDOWS.ps1.' }
    if ($Production -and !(Test-Path -LiteralPath (Join-Path $Web '.next\BUILD_ID'))) { Fail 'The production web build was not found.' 'Run BUILD ARKBYTE VOICE STUDIO WEB.cmd before starting with -Production.' }

    $token = Get-BridgeToken
    $env:ARKBYTE_BRIDGE_TOKEN = $token
    $env:ARKBYTE_BRIDGE_URL = 'http://127.0.0.1:8765'
    $env:ARKBYTE_VOICE_HOME = Join-Path $env:LOCALAPPDATA 'ArkByte Voice Studio'
    $env:HF_HOME = Join-Path $env:ARKBYTE_VOICE_HOME 'cache\huggingface'
    $env:TORCH_HOME = Join-Path $env:ARKBYTE_VOICE_HOME 'cache\torch'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $env:PYTHONPATH = $Service
    $env:NEXT_TELEMETRY_DISABLED = '1'
    New-Item -ItemType Directory -Force -Path $env:ARKBYTE_VOICE_HOME,$env:HF_HOME,$env:TORCH_HOME | Out-Null

    # Idempotency: a healthy existing ArkByte instance is success, not a startup failure.
    $backendRows = @(Get-ListenerRows 8765)
    $webRows = @(Get-ListenerRows 3000)
    if ($backendRows.Count -gt 0 -or $webRows.Count -gt 0) {
        $backendProc = if ($backendRows.Count -eq 1) { Get-ProcessById ([int]$backendRows[0].OwningProcess) } else { $null }
        $webProc = if ($webRows.Count -eq 1) { Get-ProcessById ([int]$webRows[0].OwningProcess) } else { $null }
        $backendIsOurs = ($backendRows.Count -eq 1 -and $backendRows[0].LocalAddress -eq '127.0.0.1' -and (Test-ArkByteBackend $backendProc))
        $webIsOurs = ($webRows.Count -eq 1 -and $webRows[0].LocalAddress -eq '127.0.0.1' -and (Test-ArkByteWeb $webProc))
        if ($backendIsOurs -and $webIsOurs) {
            try {
                $headers = @{ 'X-ArkByte-Token' = $token }
                $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health' -Headers $headers -TimeoutSec 4
                $null = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 4 -UseBasicParsing
                $startedUtc = (Get-Date).ToUniversalTime().ToString('o')
                try {
                    $oldOwner = Get-Content -LiteralPath (Join-Path $Run 'ownership.json') -Raw | ConvertFrom-Json
                    if ([string]$oldOwner.root -ieq $Root -and $oldOwner.started_utc) { $startedUtc = [string]$oldOwner.started_utc }
                } catch {}
                $mode = if ([string]$webProc.CommandLine -match '(?i)\sdev(\s|$)') { 'npm run dev' } else { 'npm run start' }
                Write-Ownership ([int]$backendRows[0].OwningProcess) ([int]$webRows[0].OwningProcess) ([string]$backendProc.ExecutablePath) $mode $startedUtc
                Write-Host "`nARKBYTE IS ALREADY RUNNING — no duplicate processes were started." -ForegroundColor Green
                Write-Host 'Backend: verified on 127.0.0.1:8765'
                Write-Host 'Frontend: verified on 127.0.0.1:3000'
                Write-Host 'Open: http://127.0.0.1:3000'
                Start-Process 'http://127.0.0.1:3000'
                return
            } catch {
                Fail "ArkByte processes match this project, but one or both health checks failed: $($_.Exception.Message)" 'Inspect logs\backend-error.log and logs\nextjs-error.log. Run STOP ARKBYTE VOICE STUDIO WEB.cmd, then start again.'
            }
        }
        $occupied = @()
        foreach ($row in $backendRows) { $occupied += "8765 PID $($row.OwningProcess)" }
        foreach ($row in $webRows) { $occupied += "3000 PID $($row.OwningProcess)" }
        Fail ("Port(s) already occupied: " + ($occupied -join '; ')) 'No process was changed. Use STOP ARKBYTE VOICE STUDIO WEB.cmd for a verified ArkByte session, or investigate the unrelated listener.'
    }

    $backendOut = Join-Path $Logs 'backend.log'
    $webOut = Join-Path $Logs 'nextjs.log'
    $backendErr = Join-Path $Logs 'backend-error.log'
    $webErr = Join-Path $Logs 'nextjs-error.log'
    $startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    $npmCommand = if ($Production) { 'npm run start' } else { 'npm run dev' }

    Write-Host 'Starting local Python voice service…' -ForegroundColor Cyan
    $backendArgs = "-m uvicorn main:app --app-dir `"$Service`" --host 127.0.0.1 --port 8765 --no-access-log"
    $backend = Start-Process -FilePath $Python -ArgumentList $backendArgs -WorkingDirectory $Service -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
    Set-Content -LiteralPath (Join-Path $Run 'backend.pid') -Value $backend.Id -Encoding ASCII

    Write-Host 'Waiting for local Python service…' -ForegroundColor Yellow
    $backendReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        if ($backend.HasExited) { break }
        try {
            $headers = @{ 'X-ArkByte-Token' = $token }
            $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health' -Headers $headers -TimeoutSec 2
            $rows = @(Get-ListenerRows 8765)
            if ($rows.Count -eq 1) {
                $proc = Get-ProcessById ([int]$rows[0].OwningProcess)
                if ($rows[0].LocalAddress -eq '127.0.0.1' -and (Test-ArkByteBackend $proc)) { $backendPid = [int]$rows[0].OwningProcess; $backendReady = $true; break }
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (!$backendReady) {
        $tail = if (Test-Path $backendErr) { (Get-Content $backendErr -Tail 30 | Out-String) } else { 'No backend stderr log was created.' }
        Fail "Python service did not become ready or its listener could not be verified. $tail" 'Check backend-error.log, the configured Python runtime and port 8765.'
    }

    Write-Host 'Starting Next.js web application…' -ForegroundColor Cyan
    $cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'
    $nextLauncher = Start-Process -FilePath $cmd -ArgumentList @('/d','/s','/c',$npmCommand) -WorkingDirectory $Web -PassThru -WindowStyle Hidden -RedirectStandardOutput $webOut -RedirectStandardError $webErr

    Write-Host 'Waiting for Next.js…' -ForegroundColor Yellow
    $webReady = $false
    for ($i = 0; $i -lt 90; $i++) {
        if ($nextLauncher.HasExited) {
            # npm/cmd may exit after handing off to node; readiness is determined by the listener below.
        }
        try {
            $null = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 2 -UseBasicParsing
            $rows = @(Get-ListenerRows 3000)
            if ($rows.Count -eq 1) {
                $proc = Get-ProcessById ([int]$rows[0].OwningProcess)
                if ($rows[0].LocalAddress -eq '127.0.0.1' -and (Test-ArkByteWeb $proc)) { $webPid = [int]$rows[0].OwningProcess; $webReady = $true; break }
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (!$webReady) {
        $tail = if (Test-Path $webErr) { (Get-Content $webErr -Tail 40 | Out-String) } else { 'No Next.js stderr log was created.' }
        Fail "Next.js did not become ready or its listener could not be verified. $tail" 'Check nextjs-error.log and the web build. Stop the partial ArkByte session before retrying.'
    }

    Write-Ownership $backendPid $webPid $Python $npmCommand $startedUtc
    Write-Host "`nARKBYTE VOICE STUDIO WEB IS READY" -ForegroundColor Green
    Write-Host "Mode: $(if ($Production) { 'Production' } else { 'Development' })"
    Write-Host 'Backend: verified on 127.0.0.1:8765'
    Write-Host 'Frontend: verified on 127.0.0.1:3000'
    Write-Host 'Open: http://127.0.0.1:3000'
    Write-Host "Backend log: $backendOut"
    Write-Host "Frontend log: $webOut"
    Start-Process 'http://127.0.0.1:3000'
}
catch {
    Write-Host "`nStartup failed. Cleaning up only processes created by this launch attempt..." -ForegroundColor Yellow
    foreach ($process in @($nextLauncher, $backend)) {
        if ($null -ne $process) {
            try {
                $process.Refresh()
                if (!$process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
            } catch { Write-Warning "Could not clean up launch process $($process.Id): $($_.Exception.Message)" }
        }
    }
    # If npm/cmd already exited after spawning Next.js, clean up only a listener
    # whose live command line proves it belongs to this exact project.
    foreach ($item in @(@{Port=3000; Kind='web'}, @{Port=8765; Kind='backend'})) {
        foreach ($row in @(Get-ListenerRows ([int]$item.Port))) {
            $proc = Get-ProcessById ([int]$row.OwningProcess)
            $isProjectProcess = ($row.LocalAddress -eq '127.0.0.1') -and $(if ($item.Kind -eq 'web') { Test-ArkByteWeb $proc } else { Test-ArkByteBackend $proc })
            if ($isProjectProcess) {
                try { & taskkill.exe /PID ([int]$row.OwningProcess) /T /F 2>$null | Out-Null }
                catch { Write-Warning "Could not clean up verified $($item.Kind) listener PID $($row.OwningProcess)." }
            }
        }
    }
    Start-Sleep -Seconds 2
    $remainingBackend = @(Get-ListenerRows 8765)
    $remainingWeb = @(Get-ListenerRows 3000)
    if ($remainingBackend.Count -eq 0 -and $remainingWeb.Count -eq 0) {
        Remove-Item -LiteralPath (Join-Path $Run 'ownership.json') -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $Run 'backend.pid') -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $Run 'web.pid') -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning 'A listener remains. Ownership files were retained so the Stop script can inspect the live project listeners.'
    }
    Write-Host "`nStartup error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Review logs in: $Logs" -ForegroundColor Yellow
    exit 1
}
