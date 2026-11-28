param([string]$ISCC = '', [switch]$Portable)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
Push-Location $Root
try {
    $BuildPython = Join-Path $Root '.build-venv/Scripts/python.exe'
    & $BuildPython packaging/windows/verify_distribution.py
    if ($LASTEXITCODE -ne 0) { throw 'Invalid distribution' }
    $Version = & $BuildPython -c "import runpy; print(runpy.run_path('src/browser/version.py')['__version__'])"
    if (-not $ISCC) {
        $Compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($Compiler) { $ISCC = $Compiler.Source }
        else { $ISCC = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
    }
    if (-not (Test-Path -LiteralPath $ISCC)) { throw 'Inno Setup compiler unavailable. Supply -ISCC with its installed path.' }
    & $ISCC "/DAppVersion=$Version" packaging/windows/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
    if ($Portable) {
        $Probe = Join-Path $Root 'build/windows/portable-smoke.json'
        $Process = Start-Process (Join-Path $Root 'dist/LightMq/LightMq.exe') -ArgumentList @('--release-smoke', ('"' + $Probe + '"')) -WindowStyle Hidden -PassThru
        if (-not $Process.WaitForExit(90000)) { $Process.Kill(); throw 'Portable probe timed out' }
        if ($Process.ExitCode -ne 0) { throw 'Standalone probe failed; portable archive not produced' }
        & $BuildPython -c "import shutil; shutil.make_archive('release/LightMq-Portable-$Version-x64', 'zip', 'dist', 'LightMq')"
        if ($LASTEXITCODE -ne 0) { throw 'Portable ZIP failed' }
    }
    $Artifacts = Get-ChildItem release -File | Where-Object { $_.Name -match "^LightMq-(Setup|Portable)-$([regex]::Escape($Version))-x64\.(exe|zip)$" }
    $Lines = $Artifacts | ForEach-Object { $Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(); "$Hash  $($_.Name)" }
    $Lines | Set-Content release/SHA256SUMS.txt -Encoding ascii
    Copy-Item build/windows/build-info.json release/build-info.json
    Copy-Item packaging/windows/release-notes.md release/release-notes.md
} finally { Pop-Location }
