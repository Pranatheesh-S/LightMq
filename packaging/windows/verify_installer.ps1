param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$RegistryKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{ABAA8717-87B1-4D77-90A1-64518210F92B}_is1'
if (Test-Path $RegistryKey) { throw 'An existing LightMq installation is registered. Use a clean VM instead.' }
$Target = Join-Path $Root 'build/windows/install-test'
$Report = Join-Path $Root 'build/windows/installer-smoke.json'
$Sentinel = Join-Path $Root 'build/windows/synthetic-user-data.txt'
if (Test-Path $Target) { throw 'Install-test target already exists. Inspect it before reusing this test.' }
'synthetic data must survive setup' | Set-Content -LiteralPath $Sentinel
$Installer = (Resolve-Path -LiteralPath $Installer).Path
$Group = 'LightMq Phase18 Verification'
$ExistingShortcut = Join-Path ([Environment]::GetFolderPath('Programs')) ($Group + '/LightMq.lnk')
if (Test-Path $ExistingShortcut) { throw 'A verification shortcut already exists; inspect it before testing.' }
$SetupLog = Join-Path $Root 'build/windows/setup-test.log'
$Arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $Target + '"'),('/GROUP="' + $Group + '"'),('/LOG="' + $SetupLog + '"'))
$Process = Start-Process -FilePath $Installer -ArgumentList $Arguments -WindowStyle Hidden -PassThru
if (-not $Process.WaitForExit(60000)) { throw 'Installation timed out; inspect process before cleanup' }
if ($Process.ExitCode -ne 0) { throw "Installation failed: $($Process.ExitCode)" }
$Shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) ($Group + '/LightMq.lnk')
$Checks = [ordered]@{installed=(Test-Path (Join-Path $Target 'LightMq.exe')); start_menu=(Test-Path $Shortcut)}
$Probe = Join-Path $Root 'build/windows/installed-smoke.json'
$Process = Start-Process -FilePath (Join-Path $Target 'LightMq.exe') -ArgumentList @('--release-smoke',('"'+$Probe+'"')) -WindowStyle Hidden -PassThru
if (-not $Process.WaitForExit(60000)) { throw 'Installed smoke timed out' }
$Checks['installed_probe'] = $Process.ExitCode -eq 0
$Process = Start-Process -FilePath $Installer -ArgumentList $Arguments -WindowStyle Hidden -PassThru
if (-not $Process.WaitForExit(60000)) { throw 'Reinstall timed out' }
$Checks['same_version_reinstall'] = $Process.ExitCode -eq 0
$Checks['data_survived_reinstall'] = (Get-Content -LiteralPath $Sentinel) -eq 'synthetic data must survive setup'
$Process = Start-Process -FilePath (Join-Path $Target 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -WindowStyle Hidden -PassThru
if (-not $Process.WaitForExit(60000)) { throw 'Uninstall timed out' }
$Checks['uninstall'] = $Process.ExitCode -eq 0 -and -not (Test-Path (Join-Path $Target 'LightMq.exe'))
$Checks['shortcut_removed'] = -not (Test-Path $Shortcut)
$Checks['data_survived_uninstall'] = Test-Path -LiteralPath $Sentinel
$Checks | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding utf8
Get-Content -LiteralPath $Report
if ($Checks.Values -contains $false) { throw 'Installer smoke failed' }
# Same-version reinstall is not an earlier-version upgrade test or clean-machine proof.
