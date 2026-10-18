# Builds dist\Tangerine\ (portable app) and dist\Tangerine-Setup.exe (installer).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$pkg = Join-Path $root "packaging"
$icon = Join-Path $pkg "tangerine.ico"
$dist = Join-Path $root "dist"
$work = Join-Path $root "build"

function Run($exe, $arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $exe $arguments" }
}

Write-Host "== icon"
Run $py @((Join-Path $pkg "make_icon.py"))

Write-Host "== app (PyInstaller)"
Run $py @("-m", "PyInstaller", (Join-Path $pkg "tangerine.spec"), "--noconfirm", "--distpath", $dist, "--workpath", (Join-Path $work "app"))

Remove-Item (Join-Path $work "app") -Recurse -Force -ErrorAction SilentlyContinue  # frees disk space

Write-Host "== self test of the built app"
$result = Join-Path $dist "selftest.txt"
Remove-Item $result -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath (Join-Path $dist "Tangerine\Tangerine.exe") -ArgumentList @("--selftest", "`"$result`"") -Wait -PassThru
Get-Content $result
if ($proc.ExitCode -ne 0) { throw "Self test failed" }

Write-Host "== uninstaller"
Run $py @("-m", "PyInstaller", "--noconfirm", "--onefile", "--noconsole", "--name", "Uninstall", "--icon", $icon,
    "--paths", $pkg, "--distpath", (Join-Path $work "uninstall"), "--workpath", (Join-Path $work "uninstall_work"),
    "--specpath", $work, (Join-Path $pkg "uninstall.py"))
Copy-Item (Join-Path $work "uninstall\Uninstall.exe") (Join-Path $dist "Tangerine\Uninstall.exe") -Force

Write-Host "== installer"
Run $py @((Join-Path $pkg "make_payload.py"))
# The payload holds everything; drop the unpacked copy and temp files to save disk space.
Remove-Item (Join-Path $dist "Tangerine") -Recurse -Force
Remove-Item (Join-Path $work "uninstall"), (Join-Path $work "uninstall_work") -Recurse -Force -ErrorAction SilentlyContinue
Run $py @("-m", "PyInstaller", "--noconfirm", "--onefile", "--noconsole", "--name", "Tangerine-Setup", "--icon", $icon,
    "--paths", $pkg, "--add-data", ((Join-Path $work "payload.zip") + ";."), "--distpath", $dist,
    "--workpath", (Join-Path $work "installer_work"), "--specpath", $work, (Join-Path $pkg "installer.py"))

Write-Host "Done: dist\Tangerine-Setup.exe"
