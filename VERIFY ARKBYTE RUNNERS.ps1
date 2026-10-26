[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$failed = $false

$scriptFiles = @(
    'Collect-ArkByte-Source.ps1',
    'START ARKBYTE VOICE STUDIO WEB.ps1',
    'STOP ARKBYTE VOICE STUDIO WEB.ps1',
    'RUN ARKBYTE VOICE STUDIO.ps1'
)
$scriptText = @{}

foreach ($name in $scriptFiles) {
    $path = Join-Path $Root $name
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-Host "MISSING: $name" -ForegroundColor Red
        $failed = $true
        continue
    }
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        Write-Host "SYNTAX ERROR: $name" -ForegroundColor Red
        foreach ($errorItem in $errors) {
            Write-Host ("  Line {0}: {1}" -f $errorItem.Extent.StartLineNumber, $errorItem.Message)
        }
        $failed = $true
    } else {
        Write-Host "PowerShell syntax OK: $name" -ForegroundColor Green
    }
    $scriptText[$name] = Get-Content -LiteralPath $path -Raw
}

$wrapperFiles = @(
    'START ARKBYTE VOICE STUDIO WEB.cmd',
    'STOP ARKBYTE VOICE STUDIO WEB.cmd',
    'RUN ARKBYTE VOICE STUDIO.cmd'
)
foreach ($name in $wrapperFiles) {
    $path = Join-Path $Root $name
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-Host "MISSING: $name" -ForegroundColor Red
        $failed = $true
        continue
    }
    $body = Get-Content -LiteralPath $path -Raw
    if ($body -notmatch '(?i)-ExecutionPolicy\s+Bypass' -or $body -notmatch '%~dp0') {
        Write-Host "WRAPPER CHECK FAILED: $name" -ForegroundColor Red
        $failed = $true
    } else {
        Write-Host "CMD wrapper OK: $name" -ForegroundColor Green
    }
}

# Run logic checks only when every required script was successfully read.
if ($scriptText.Count -eq $scriptFiles.Count) {
    $required = @(
        @{ Name='Collector excludes gallery backups'; Text=$scriptText['Collect-ArkByte-Source.ps1']; Pattern='gallery-backup' },
        @{ Name='Collector uses ZIP API for hidden files'; Text=$scriptText['Collect-ArkByte-Source.ps1']; Pattern='ZipFile\]::CreateFromDirectory' },
        @{ Name='Start validates bridge token length'; Text=$scriptText['START ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='value\.Length\s+-lt\s+32' },
        @{ Name='Start checks backend and frontend identity'; Text=$scriptText['START ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='(?s)Test-ArkByteBackend.*Test-ArkByteWeb' },
        @{ Name='Start has idempotent already-running branch'; Text=$scriptText['START ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='ALREADY RUNNING' },
        @{ Name='Start records actual listener PIDs'; Text=$scriptText['START ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='Write-Ownership\s+\$backendPid\s+\$webPid' },
        @{ Name='Stop discovers current listeners'; Text=$scriptText['STOP ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='Get-VerifiedProjectListener' },
        @{ Name='Stop rechecks listener before termination'; Text=$scriptText['STOP ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='Re-read both the listener and process' },
        @{ Name='Stop requires typed confirmation'; Text=$scriptText['STOP ARKBYTE VOICE STUDIO WEB.ps1']; Pattern='STOP ARKBYTE' },
        @{ Name='One-click runner checks existing healthy instance'; Text=$scriptText['RUN ARKBYTE VOICE STUDIO.ps1']; Pattern='ALREADY RUNNING AND HEALTHY' }
    )
    foreach ($check in $required) {
        if ($check.Text -notmatch $check.Pattern) {
            Write-Host "LOGIC MARKER FAILED: $($check.Name)" -ForegroundColor Red
            $failed = $true
        } else {
            Write-Host "Logic marker OK: $($check.Name)" -ForegroundColor Green
        }
    }
}

if ($failed) {
    Write-Host 'Runner verification failed. Do not use the updated runners until errors are resolved.' -ForegroundColor Red
    exit 1
}
Write-Host 'All PowerShell parser, wrapper, and structural checks passed. This is not a live start/stop test; no app process was started or stopped.' -ForegroundColor Green
