param([string]$Python = 'python', [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
Push-Location $Root
try {
    if (-not (Test-Path '.build-venv/Scripts/python.exe')) {
        & $Python -m venv .build-venv
        if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
    }
    $BuildPython = Join-Path $Root '.build-venv/Scripts/python.exe'
    & $BuildPython -c "import sys,struct; assert sys.platform=='win32' and sys.version_info[:2]==(3,12) and struct.calcsize('P')==8"
    if ($LASTEXITCODE -ne 0) { throw 'Requires Windows x64 Python 3.12' }
    if (-not $SkipInstall) {
        & $BuildPython -m pip install -r packaging/windows/requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
    }
    & $BuildPython packaging/windows/prepare.py
    if ($LASTEXITCODE -ne 0) { throw 'Asset preparation failed' }
    & $BuildPython -m PyInstaller --noconfirm --clean --workpath build/windows/pyinstaller --distpath dist packaging/windows/LightMq.spec
    if ($LASTEXITCODE -ne 0) { throw 'Standalone build failed' }
    & $BuildPython packaging/windows/verify_distribution.py
    if ($LASTEXITCODE -ne 0) { throw 'Distribution verification failed' }
} finally { Pop-Location }
