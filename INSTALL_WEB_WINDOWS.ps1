[CmdletBinding()]
param(
    [switch]$InstallAI,
    [switch]$ForceNewEnvironment,
    [string]$PythonPath
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root 'web'
$Service = Join-Path $Root 'service'
$Logs = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$Log = Join-Path $Logs ("web-install-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Start-Transcript -Path $Log -Force | Out-Null

function Write-Step([string]$Message) { Write-Host "`n>>> $Message" -ForegroundColor Cyan }
function Invoke-NativeCapture([string]$File, [string[]]$Arguments) {
    # Windows PowerShell 5.1 can promote native stderr text to terminating
    # PowerShell errors when ErrorActionPreference is Stop. Capture it safely
    # and use the native process exit code as the source of truth.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $File @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        return [pscustomobject]@{ ExitCode = [int]$exitCode; Output = (($output | Out-String).Trim()) }
    } catch {
        return [pscustomobject]@{ ExitCode = 1; Output = $_.Exception.Message }
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}
function Invoke-NativeChecked([string]$File, [string[]]$Arguments, [string]$Failure, [string]$Advice) {
    $result = Invoke-NativeCapture -File $File -Arguments $Arguments
    if ($result.Output) { Write-Host $result.Output }
    if ($result.ExitCode -ne 0) { Stop-WithHelp $Failure $Advice }
    return $result
}
function Stop-WithHelp([string]$Message, [string]$Action) {
    Write-Host "`nINSTALLATION STOPPED: $Message" -ForegroundColor Red
    Write-Host "Recommended action: $Action" -ForegroundColor Yellow
    Write-Host "Diagnostic log: $Log" -ForegroundColor Gray
    try { Stop-Transcript | Out-Null } catch {}
    throw $Message
}

try {
    Write-Host 'ARKBYTE VOICE STUDIO WEB - WINDOWS SETUP' -ForegroundColor Green
    Write-Host 'Local-first web edition. No paid API or subscription is used.'

    Write-Step 'Checking Windows architecture and disk space'
    if ([Environment]::Is64BitOperatingSystem -ne $true) {
        Stop-WithHelp 'A 64-bit Windows installation is required.' 'Use a supported Windows 10/11 x64 PC.'
    }
    $drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($Root).Substring(0,1))
    $requiredFreeSpace = if ($InstallAI) { 15GB } else { 8GB }
    if ($drive.Free -lt $requiredFreeSpace) {
        Stop-WithHelp "Less than $([math]::Round($requiredFreeSpace / 1GB)) GB of free disk space is available for this install mode." 'Free disk space and rerun setup. AI packages and model weights require additional storage.'
    }

    Write-Step 'Checking Node.js'
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (!$node) {
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (!$winget) { Stop-WithHelp 'Node.js and Windows Package Manager were not found.' 'Install Node.js 22 LTS or newer from https://nodejs.org, then rerun setup.' }
        $wingetResult = Invoke-NativeCapture -File $winget.Source -Arguments @('install','--id','OpenJS.NodeJS.LTS','--exact','--accept-package-agreements','--accept-source-agreements')
        if ($wingetResult.Output) { Write-Host $wingetResult.Output }
        if ($wingetResult.ExitCode -ne 0) { Stop-WithHelp 'Node.js installation failed.' 'Install Node.js 22 LTS manually from https://nodejs.org, then reopen PowerShell and rerun this script.' }
        $nodeCandidates = @("$env:ProgramFiles\nodejs\node.exe", "$env:LOCALAPPDATA\Programs\nodejs\node.exe")
        foreach ($candidate in $nodeCandidates) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $env:PATH = "$(Split-Path $candidate -Parent);$env:PATH" }
        }
        $node = Get-Command node.exe -ErrorAction SilentlyContinue
    }
    if (!$node) { Stop-WithHelp 'Node.js is still not visible in PATH.' 'Close PowerShell, open a new window, and rerun INSTALL_WEB_WINDOWS.ps1.' }
    $nodeVersionResult = Invoke-NativeCapture -File $node.Source -Arguments @('--version')
    $nodeVersion = $nodeVersionResult.Output
    if ($nodeVersionResult.ExitCode -ne 0) { Stop-WithHelp 'Node.js could not be executed.' 'Repair Node.js LTS from https://nodejs.org, reopen PowerShell, and retry.' }
    $nodeMajor = 0
    $nodeMinor = 0
    if ($nodeVersion -match 'v?(\d+)\.(\d+)') { $nodeMajor = [int]$Matches[1]; $nodeMinor = [int]$Matches[2] }
    if ($nodeMajor -lt 20 -or ($nodeMajor -eq 20 -and $nodeMinor -lt 9)) {
        Stop-WithHelp "Node.js $nodeVersion is too old for this Next.js release." 'Install Node.js 22 LTS or newer from https://nodejs.org, reopen PowerShell, and rerun setup.'
    }
    Write-Host "Node.js: $nodeVersion"

    Write-Step 'Checking FFmpeg and FFprobe'
    $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    $ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
    if (!$ffmpeg -or !$ffprobe) {
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (!$winget) { Stop-WithHelp 'FFmpeg and FFprobe are required for video/audio imports.' 'Install a trusted Windows FFmpeg build and add its bin folder to PATH, then rerun setup.' }
        $mediaInstall = Invoke-NativeCapture -File $winget.Source -Arguments @('install','--id','Gyan.FFmpeg','--exact','--accept-package-agreements','--accept-source-agreements')
        if ($mediaInstall.Output) { Write-Host $mediaInstall.Output }
        if ($mediaInstall.ExitCode -ne 0) { Stop-WithHelp 'FFmpeg could not be installed by Windows Package Manager.' 'Install FFmpeg manually from https://www.gyan.dev/ffmpeg/builds/ and add its bin folder to PATH, then rerun setup.' }
        # Refresh this process PATH from the Windows environment so the current
        # setup can validate the tools without requiring a shell restart.
        $machinePath = [Environment]::GetEnvironmentVariable('Path','Machine')
        $userPath = [Environment]::GetEnvironmentVariable('Path','User')
        if ($machinePath -or $userPath) { $env:PATH = (@($machinePath,$userPath,$env:PATH) -join ';') }
        $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
        $ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
        if (!$ffmpeg -or !$ffprobe) {
            $wingetRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
            $bundle = if (Test-Path $wingetRoot) { Get-ChildItem -LiteralPath $wingetRoot -Directory -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue | Select-Object -First 1 } else { $null }
            if ($bundle) {
                $ffmpegFile = Get-ChildItem -LiteralPath $bundle.FullName -Filter 'ffmpeg.exe' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($ffmpegFile) { $env:PATH = "$(Split-Path $ffmpegFile.FullName -Parent);$env:PATH" }
            }
            $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
            $ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
        }
    }
    if (!$ffmpeg -or !$ffprobe) { Stop-WithHelp 'FFmpeg or FFprobe is still not available after setup.' 'Restart Windows or add the FFmpeg bin folder to PATH, then rerun INSTALL_WEB_WINDOWS.ps1.' }
    $ffmpegCheck = Invoke-NativeCapture -File $ffmpeg.Source -Arguments @('-version')
    $ffprobeCheck = Invoke-NativeCapture -File $ffprobe.Source -Arguments @('-version')
    if ($ffmpegCheck.ExitCode -ne 0 -or $ffprobeCheck.ExitCode -ne 0) { Stop-WithHelp 'The media tools were found but could not run.' 'Reinstall FFmpeg from a trusted build and confirm both ffmpeg.exe and ffprobe.exe are present.' }
    Write-Host "FFmpeg: $($ffmpeg.Source)" -ForegroundColor Green
    Write-Host "FFprobe: $($ffprobe.Source)" -ForegroundColor Green

    Write-Step 'Preparing an isolated Python runtime'

    # Keep the web service isolated from the desktop application's venv.
    # Both applications can still use the same ARKBYTE_VOICE_HOME data root.
    $venvPath = Join-Path $Root '.venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    if ($ForceNewEnvironment -and (Test-Path -LiteralPath $venvPath)) {
        $backupPath = "$venvPath.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Move-Item -LiteralPath $venvPath -Destination $backupPath
        Write-Host "Previous web environment preserved at: $backupPath" -ForegroundColor Yellow
    }

    function Find-ValidPythonRuntime {
        param([string]$PreferredPath)
        $candidates = New-Object System.Collections.Generic.List[string]
        if ($PreferredPath) { [void]$candidates.Add($PreferredPath) }

        # Search executable commands first, but validate every candidate. This
        # intentionally rejects the Microsoft Store python.exe execution alias.
        foreach ($commandName in @('python.exe','python3.exe')) {
            $commands = @(Get-Command $commandName -All -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' })
            foreach ($command in $commands) { if ($command.Source) { [void]$candidates.Add($command.Source) } }
        }

        # The Python launcher knows about custom install locations; do not rely
        # only on a few hard-coded python.org paths.
        $runtimeProbeScript = Join-Path $Root 'verify_python_runtime.py'
        if (!(Test-Path -LiteralPath $runtimeProbeScript -PathType Leaf)) {
            Stop-WithHelp 'The Python runtime verification script is missing from this package.' 'Re-download the complete, checksum-verified ArkByte hotfix ZIP.'
        }
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            $listing = Invoke-NativeCapture -File $launcher.Source -Arguments @('-0p')
            foreach ($line in ($listing.Output -split "`r?`n")) {
                $match = [regex]::Match($line, '(?i)([A-Z]:\\.*?python\.exe)')
                if ($match.Success) { [void]$candidates.Add($match.Groups[1].Value.Trim()) }
            }
            foreach ($version in @('3.12','3.13')) {
                $exe = Invoke-NativeCapture -File $launcher.Source -Arguments @("-$version",$runtimeProbeScript)
                if ($exe.ExitCode -eq 0 -and $exe.Output) {
                    $resolvedLine = $exe.Output -split "`r?`n" | Where-Object { $_ -match '(?i)python\.exe$' } | Select-Object -Last 1
                    if ($resolvedLine) { [void]$candidates.Add($resolvedLine.Trim()) }
                }
            }
        }

        # Standard Python.org registry locations (per-user and machine-wide).
        foreach ($registryPath in @(
            'HKCU:\Software\Python\PythonCore\3.12\InstallPath',
            'HKCU:\Software\Python\PythonCore\3.13\InstallPath',
            'HKLM:\Software\Python\PythonCore\3.12\InstallPath',
            'HKLM:\Software\Python\PythonCore\3.13\InstallPath',
            'HKLM:\Software\WOW6432Node\Python\PythonCore\3.12\InstallPath',
            'HKLM:\Software\WOW6432Node\Python\PythonCore\3.13\InstallPath'
        )) {
            $key = Get-Item -LiteralPath $registryPath -ErrorAction SilentlyContinue
            if ($key) {
                $installDirectory = [string]$key.GetValue('')
                if ($installDirectory) { [void]$candidates.Add((Join-Path $installDirectory 'python.exe')) }
            }
        }

        foreach ($candidate in @(
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
            "$env:ProgramFiles\Python312\python.exe",
            "$env:ProgramFiles\Python313\python.exe",
            'C:\Python312\python.exe',
            'C:\Python313\python.exe'
        )) { [void]$candidates.Add($candidate) }

        $seen = @{}
        foreach ($candidate in $candidates) {
            if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
            $candidate = $candidate.Trim().Trim('"')
            $key = $candidate.ToLowerInvariant()
            if ($seen.ContainsKey($key)) { continue }
            $seen[$key] = $true
            if (!(Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
            $probe = Invoke-NativeCapture -File $candidate -Arguments @($runtimeProbeScript)
            if ($probe.ExitCode -eq 0) {
                $resolved = ($probe.Output -split "`r?`n" | Where-Object { $_ -match '(?i)python\.exe$' } | Select-Object -Last 1)
                if ($resolved -and (Test-Path -LiteralPath $resolved.Trim() -PathType Leaf)) { return $resolved.Trim() }
            }
        }
        return $null
    }

    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $python = $venvPython
        Write-Host 'Reusing the existing web-only virtual environment.' -ForegroundColor Green
    } else {
        $basePython = Find-ValidPythonRuntime -PreferredPath $PythonPath

        if (!$basePython) {
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if ($winget) {
                Write-Host 'No supported runtime was discovered. Checking the Python 3.12 package with WinGet...' -ForegroundColor Yellow
                $pythonInstall = Invoke-NativeCapture -File $winget.Source -Arguments @('install','--id','Python.Python.3.12','--exact','--scope','user','--accept-package-agreements','--accept-source-agreements')
                if ($pythonInstall.Output) { Write-Host $pythonInstall.Output }
                # Refresh PATH from both scopes in case the installer just added
                # Python to PATH. Then search commands, launcher, registry and paths again.
                $machinePath = [Environment]::GetEnvironmentVariable('Path','Machine')
                $userPath = [Environment]::GetEnvironmentVariable('Path','User')
                if ($machinePath -or $userPath) { $env:PATH = (@($machinePath,$userPath,$env:PATH) -join ';') }
                $basePython = Find-ValidPythonRuntime -PreferredPath $PythonPath
            }
        }

        if (!$basePython -or !(Test-Path -LiteralPath $basePython -PathType Leaf)) {
            Stop-WithHelp 'Python 3.12 or 3.13 x64 was not found.' 'Run: py -0p and Get-Command python.exe -All. If Python 3.12 x64 is installed, rerun with -PythonPath "C:\full\path\to\python.exe". Otherwise install Python 3.12 x64 from https://www.python.org/downloads/windows/.'
        }
        $pythonProbe = Invoke-NativeCapture -File $basePython -Arguments @((Join-Path $Root 'verify_python_runtime.py'))
        if ($pythonProbe.Output) { Write-Host $pythonProbe.Output }
        if ($pythonProbe.ExitCode -ne 0) { Stop-WithHelp 'The selected Python runtime is unsupported or not 64-bit.' 'Install Python 3.12 or 3.13 x64 and rerun setup.' }

        Write-Host "Creating isolated web environment from: $basePython" -ForegroundColor Green
        $venvResult = Invoke-NativeCapture -File $basePython -Arguments @('-m','venv',$venvPath)
        if ($venvResult.Output) { Write-Host $venvResult.Output }
        if ($venvResult.ExitCode -ne 0 -or !(Test-Path -LiteralPath $venvPython -PathType Leaf)) {
            Stop-WithHelp 'Could not create the isolated web Python environment.' 'Check folder permissions and available disk space, then rerun setup.'
        }
        $python = $venvPython
    }
    $pythonProbe = Invoke-NativeCapture -File $python -Arguments @((Join-Path $Root 'verify_python_runtime.py'))
    if ($pythonProbe.Output) { Write-Host $pythonProbe.Output }
    if ($pythonProbe.ExitCode -ne 0) { Stop-WithHelp 'The web virtual environment is unsupported or damaged.' 'Rerun INSTALL_WEB_WINDOWS.ps1 -ForceNewEnvironment. The previous environment is preserved as a backup.' }
    Write-Host "Web Python environment: $python" -ForegroundColor Green

    Write-Step 'Installing Python service dependencies'
    Invoke-NativeChecked -File $python -Arguments @('-m','pip','install','--upgrade','pip','wheel') -Failure 'pip could not be upgraded.' -Advice 'Check internet access and retry. Existing creator data is untouched.' | Out-Null
    Invoke-NativeChecked -File $python -Arguments @('-m','pip','install','-r',(Join-Path $Service 'requirements.txt')) -Failure 'Python web-service dependencies failed to install.' -Advice 'Check the installer log, network access, and Python version; rerun this script to repair.' | Out-Null

    if ($InstallAI) {
        Write-Step 'Installing local Chatterbox AI engine'
        Invoke-NativeChecked -File $python -Arguments @('-m','pip','install','-r',(Join-Path $Service 'requirements-ai.txt')) -Failure 'Chatterbox AI dependencies failed to install.' -Advice 'Check GPU drivers and free disk space. See docs/AI-ENGINE.md; rerun with -InstallAI to retry.' | Out-Null
        $aiVerifyScript = Join-Path $Root 'verify_ai_engine.py'
        if (!(Test-Path -LiteralPath $aiVerifyScript -PathType Leaf)) {
            Stop-WithHelp 'The AI verification script is missing from this package.' 'Re-download the complete, checksum-verified ArkByte hotfix ZIP.'
        }
        # Invoke a .py file instead of `python -c` with quoted print labels.
        # Windows PowerShell 5.1 may strip inner quotes from native -c arguments,
        # turning print("PyTorch", ...) into print(PyTorch, ...) and raising NameError.
        Invoke-NativeChecked -File $python -Arguments @($aiVerifyScript) -Failure 'Chatterbox or PyTorch did not import after installation.' -Advice 'Read the traceback immediately above this message. Confirm that the isolated environment can import torch and chatterbox.mtl_tts; do not reinstall Python blindly.' | Out-Null
    } else {
        Write-Host 'AI dependency install deferred. To install it, rerun with -InstallAI.' -ForegroundColor Yellow
    }

    Write-Step 'Installing Next.js packages'
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (!$npmCommand) { Stop-WithHelp 'npm.cmd was not found after Node.js setup.' 'Repair Node.js LTS from https://nodejs.org, reopen PowerShell, and rerun setup.' }
    Push-Location $Web
    try {
        if (Test-Path 'package-lock.json') { $npmArgs = @('ci') } else { $npmArgs = @('install','--no-audit','--no-fund') }
        Invoke-NativeChecked -File $npmCommand.Source -Arguments $npmArgs -Failure 'npm dependency installation failed.' -Advice 'Check internet access, run npm cache verify, then rerun setup.' | Out-Null
    } finally { Pop-Location }

    Write-Step 'Creating private local bridge credentials'
    $envFile = Join-Path $Web '.env.local'
    if (!(Test-Path $envFile)) {
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $token = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
        @("ARKBYTE_BRIDGE_TOKEN=$token", 'ARKBYTE_BRIDGE_URL=http://127.0.0.1:8765') | Set-Content -LiteralPath $envFile -Encoding ascii
    }
    $runtimeFile = Join-Path $Root 'python-runtime.txt'
    Set-Content -LiteralPath $runtimeFile -Value $python -Encoding UTF8
    $env:ARKBYTE_VOICE_HOME = Join-Path $env:LOCALAPPDATA 'ArkByte Voice Studio'
    New-Item -ItemType Directory -Force -Path $env:ARKBYTE_VOICE_HOME | Out-Null

    Write-Step 'Running preflight checks'
    $backendVerifyScript = Join-Path $Root 'verify_backend_preflight.py'
    if (!(Test-Path -LiteralPath $backendVerifyScript -PathType Leaf)) {
        Stop-WithHelp 'The backend verification script is missing from this package.' 'Re-download the complete, checksum-verified ArkByte hotfix ZIP.'
    }
    Invoke-NativeChecked -File $python -Arguments @($backendVerifyScript) -Failure 'Python backend preflight failed.' -Advice 'Read the traceback immediately above this message and repair the missing or incompatible backend package.' | Out-Null
    Push-Location $Web
    try { Invoke-NativeChecked -File $npmCommand.Source -Arguments @('run','typecheck') -Failure 'Next.js TypeScript validation failed.' -Advice 'Open the installer transcript and share the TypeScript error.' | Out-Null }
    finally { Pop-Location }

    Write-Host "`nSETUP COMPLETED" -ForegroundColor Green
    Write-Host 'Next: double-click START ARKBYTE VOICE STUDIO WEB.cmd.'
    if (!$InstallAI) { Write-Host 'For full voice generation, rerun: .\INSTALL_WEB_WINDOWS.ps1 -InstallAI' -ForegroundColor Yellow }
    Write-Host "Logs: $Log"
    Stop-Transcript | Out-Null
}
catch {
    Write-Host "`nSETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Recommended recovery: review $Log and rerun this script after correcting the reported prerequisite." -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
