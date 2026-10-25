$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root 'web'
$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (!$Npm) { throw 'npm.cmd was not found. Install Node.js 22 LTS or newer, reopen PowerShell, and rerun setup.' }
if (!(Test-Path (Join-Path $Web 'node_modules'))) { throw 'Web dependencies are missing. Run INSTALL_WEB_WINDOWS.ps1 first.' }
Push-Location $Web
try {
    Write-Host "`nChecking TypeScript types…" -ForegroundColor Cyan
    & npm.cmd run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'TypeScript validation failed. Review the reported errors before building.' }
    Write-Host "`nBuilding production Next.js app…" -ForegroundColor Cyan
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Next.js production build failed. Review the output and logs.' }
    if (!(Test-Path (Join-Path $Web '.next\BUILD_ID'))) { throw 'Build completed without a Next.js BUILD_ID. Do not use production mode yet.' }
    Write-Host "`nPRODUCTION BUILD SUCCESSFUL" -ForegroundColor Green
    Write-Host 'Start with: powershell -ExecutionPolicy Bypass -File "START ARKBYTE VOICE STUDIO WEB.ps1" -Production'
} finally { Pop-Location }
