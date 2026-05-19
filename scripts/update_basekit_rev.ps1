$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $repoRoot
try {
    uv lock --upgrade-package basekit
    uv sync
}
finally {
    Pop-Location
}

Write-Host "basekit lockfile and environment are updated."
