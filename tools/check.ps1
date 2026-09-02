$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VirtualEnvironmentPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VirtualEnvironmentPython) {
    $VirtualEnvironmentPython
} else {
    "python"
}

Push-Location $ProjectRoot
try {
    & $Python -m ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed." }

    & $Python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint check failed." }

    & $Python -m mypy
    if ($LASTEXITCODE -ne 0) { throw "Mypy check failed." }

    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }
} finally {
    Pop-Location
}
