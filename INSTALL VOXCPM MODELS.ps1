[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$pythonFile = Join-Path $Root 'python-runtime.txt'
if (!(Test-Path -LiteralPath $pythonFile)) { throw 'python-runtime.txt is missing. Set it to the existing Python runtime first.' }
$Python = (Get-Content -LiteralPath $pythonFile -Raw).Trim()
if (![System.IO.Path]::IsPathRooted($Python)) { $Python = Join-Path $Root $Python }
$Python = [System.IO.Path]::GetFullPath($Python)
if (!(Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Configured Python does not exist: $Python" }

$version = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0 -or [Version]$version -lt [Version]'3.10' -or [Version]$version -ge [Version]'3.13') {
    throw "VoxCPM currently documents Python 3.10-3.12. Configured runtime is $version. No packages were changed."
}
$torchInfo = & $Python -c "import torch, torchaudio; print(torch.__version__); print(torchaudio.__version__); print(torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'PyTorch and torchaudio must already be installed in the configured environment. No package was installed.' }
$torchLines = @($torchInfo)
Write-Host "Python: $version" -ForegroundColor Green
Write-Host "Torch: $($torchLines[0]) | Torchaudio: $($torchLines[1]) | CUDA: $($torchLines[2])"

$temp = Join-Path $env:TEMP ("arkbyte-voxcpm-constraints-{0}" -f [Guid]::NewGuid().ToString('N'))
$constraints = Join-Path $temp 'constraints.txt'
$report = Join-Path $temp 'pip-plan.json'
New-Item -ItemType Directory -Force -Path $temp | Out-Null
try {
    $protected = @('torch','torchaudio','torchvision','numpy','triton','xformers')
    $constraintCode = 'import importlib.metadata as m, pathlib, sys; rows = [d.metadata.get("Name") + "==" + d.version for d in m.distributions() if d.metadata.get("Name")]; pathlib.Path(sys.argv[1]).write_text("\n".join(sorted(set(rows))) + "\n", encoding="ascii")'
    & $Python -c $constraintCode $constraints
    if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $constraints)) { throw 'Could not freeze the existing Python package set. No installation was performed.' }
    Write-Host "`nChecking the optional VoxCPM 2.0.3 dependency plan without installing anything..." -ForegroundColor Cyan
    & $Python -m pip install --dry-run --report $report --constraint $constraints 'voxcpm==2.0.3'
    if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $report)) { throw 'Pip could not resolve the optional package safely. No installation was performed.' }
    $plan = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    $changes = @($plan.install | ForEach-Object { "{0} {1}" -f $_.metadata.name,$_.metadata.version })
    $unsafe = @($plan.install | Where-Object { $protected -contains ([string]$_.metadata.name).ToLowerInvariant() })
    if ($unsafe.Count -gt 0) {
        $names = ($unsafe | ForEach-Object { $_.metadata.name }) -join ', '
        throw "The plan would modify protected runtime packages: $names. Installation aborted; your CUDA/PyTorch stack was not changed."
    }
    Write-Host "`nPackages proposed for install/update:"
    $changes | ForEach-Object { Write-Host "  $_" }
    Write-Host "`nAll already-installed Python package versions are constrained; the existing CUDA/PyTorch stack cannot be upgraded by this run."
    $answer = Read-Host 'Proceed with installing VoxCPM Python packages? Type YES to continue'
    if ($answer -cne 'YES') { Write-Host 'Cancelled. No package installation was performed.' -ForegroundColor Yellow; return }
    & $Python -m pip install --constraint $constraints 'voxcpm==2.0.3'
    if ($LASTEXITCODE -ne 0) { throw 'VoxCPM package installation failed. Review pip output; the existing core runtime versions were pinned.' }
    & $Python -c "from voxcpm import VoxCPM; print('VoxCPM import: OK')"
    if ($LASTEXITCODE -ne 0) { throw 'VoxCPM package is installed but its import test failed.' }
    Write-Host "`nVoxCPM package installation completed. The voice model weights have NOT been downloaded yet; they are fetched on first generation." -ForegroundColor Green
    Write-Host 'Restart ArkByte and refresh Settings. Start with VoxCPM 0.5B; the 2B checkpoint is not a good fit for a 6 GB GPU.'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
