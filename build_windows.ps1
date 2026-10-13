# Build the single-EXE Windows app.
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m pip install --quiet pyinstaller pyserial PyQt6
& $py -m PyInstaller --noconfirm --clean EasyPhoneUnlock.spec

Write-Host ""
Write-Host "[+] Built: dist\EasyPhoneUnlock.exe"
