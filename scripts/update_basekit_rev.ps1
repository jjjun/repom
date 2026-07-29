$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $repoRoot
try {
    # $ErrorActionPreference does not apply to native command exit codes on
    # Windows PowerShell 5.1, so check $LASTEXITCODE after every uv call.
    uv lock --upgrade-package basekit
    $uvExitCode = $LASTEXITCODE
    if ($uvExitCode -ne 0) {
        Write-Warning "uv lock --upgrade-package basekit failed (exit $uvExitCode)."
        exit $uvExitCode
    }

    # --all-extras keeps optional feature dependencies installed.
    uv sync --all-extras --dev
    $uvExitCode = $LASTEXITCODE
    if ($uvExitCode -ne 0) {
        Write-Warning "uv sync failed (exit $uvExitCode). An 'Access is denied' error can mean something is running from .venv; stop it and re-run: uv sync --all-extras --dev"
        exit $uvExitCode
    }
}
finally {
    Pop-Location
}

Write-Host "basekit lockfile and environment are updated."
