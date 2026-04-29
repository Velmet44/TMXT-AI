$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $root "..\.."))
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$distRoot = Join-Path $projectRoot "apps\dist\coordinator"
$workRoot = Join-Path $root "build"

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

Push-Location $root
try {
  & $python -m PyInstaller --clean --noconfirm --distpath $distRoot --workpath $workRoot coordinator.spec
} finally {
  Pop-Location
}
