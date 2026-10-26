[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$OutputDirectory = (Join-Path $env:USERPROFILE 'Desktop')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot"
}
if (-not (Test-Path -LiteralPath $OutputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\')
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stage = Join-Path $env:TEMP "ArkByte-Source-$stamp-$([Guid]::NewGuid().ToString('N'))"
$zipPath = Join-Path $OutputDirectory "ArkByte-Voice-Studio-source-$stamp.zip"
New-Item -ItemType Directory -Path $stage -Force | Out-Null

$excludedDirectories = @(
    '.git', '.venv', '.venv-cuda-test', 'venv', 'node_modules', '.next', '.vercel',
    '.local-backups', 'logs', 'run', '__pycache__', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', 'cache', 'model-cache', 'checkpoints', 'weights', 'outputs',
    'imports', 'profiles', 'recordings', 'voice-recordings', 'generated-audio'
)
$excludedExtensions = @(
    '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.aac', '.wma',
    '.pt', '.pth', '.ckpt', '.safetensors', '.onnx', '.engine', '.gguf', '.bin',
    '.sqlite', '.sqlite3', '.db', '.db-shm', '.db-wal', '.msix', '.exe', '.pfx', '.key'
)
$excludedNames = @(
    'python-runtime.txt', '*.pid', '*.log', '*.tsbuildinfo', '*.backup-*',
    '*.gallery-backup-*', '*.bak', '*.pem', '*.cer', '*.p12', '*.pfx'
)

$copied = 0
$skipped = 0
try {
    $files = Get-ChildItem -LiteralPath $ProjectRoot -File -Recurse -Force
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($ProjectRoot.Length).TrimStart('\')
        $parts = $relative -split '[\\/]'
        $skip = $false

        if ($parts.Count -gt 1) {
            foreach ($part in $parts[0..($parts.Count - 2)]) {
                if ($excludedDirectories -contains $part -or $part -like '.venv-*') {
                    $skip = $true
                    break
                }
            }
        }

        if (-not $skip -and $excludedExtensions -contains $file.Extension.ToLowerInvariant()) { $skip = $true }
        if (-not $skip) {
            foreach ($pattern in $excludedNames) {
                if ($file.Name -like $pattern) { $skip = $true; break }
            }
        }
        if (-not $skip -and $file.Name -like '.env*' -and $file.Name -ne '.env.example') { $skip = $true }

        if ($skip) { $skipped++; continue }

        $destination = Join-Path $stage $relative
        $destinationDirectory = Split-Path -Parent $destination
        if (-not (Test-Path -LiteralPath $destinationDirectory)) {
            New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
        $copied++
    }

    if ($copied -eq 0) { throw 'No project files were collected. Verify ProjectRoot.' }

    # ZipFile.CreateFromDirectory includes hidden files (for example .gitignore and
    # .env.example); Compress-Archive wildcard expansion can omit hidden files.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $stage, $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )

    $zip = Get-Item -LiteralPath $zipPath
    Write-Host ''
    Write-Host 'ARKBYTE SOURCE BUNDLE CREATED' -ForegroundColor Green
    Write-Host "File: $zipPath"
    Write-Host "Included files: $copied"
    Write-Host "Excluded files: $skipped"
    Write-Host ("Archive size: {0:N1} MB" -f ($zip.Length / 1MB))
    Write-Host ''
    Write-Host 'Inspect the ZIP before sharing. Confirm it contains no private recordings, credentials, or personal data.' -ForegroundColor Yellow
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
