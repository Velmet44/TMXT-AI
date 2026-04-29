$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $root "..\.."))
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$distRoot = Join-Path $projectRoot "apps\dist\coordinator"
$workRoot = Join-Path $root "build"
$envExampleSource = Join-Path $root ".env.example"
$envExampleTarget = Join-Path $distRoot "coordinator.env.example"
$ngrokSource = Join-Path $root "ngrok.exe"
$ngrokTarget = Join-Path $distRoot "ngrok.exe"

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

Push-Location $root
try {
  & $python -m PyInstaller --clean --noconfirm --distpath $distRoot --workpath $workRoot coordinator.spec
  if (Test-Path $envExampleSource) {
    Copy-Item -LiteralPath $envExampleSource -Destination $envExampleTarget -Force
  }
  if (Test-Path $ngrokSource) {
    Copy-Item -LiteralPath $ngrokSource -Destination $ngrokTarget -Force
  }
} finally {
  Pop-Location
}
