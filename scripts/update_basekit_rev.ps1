param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoUrl = "https://github.com/jjjun/basekit.git"
$branch = "main"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pyprojectPath = Join-Path $repoRoot "pyproject.toml"

Write-Host "Fetching latest basekit revision from $repoUrl ($branch)..."
$remoteLine = git ls-remote $repoUrl "refs/heads/$branch"
if (-not $remoteLine) {
    throw "Could not resolve $branch from $repoUrl"
}

$latestRev = ($remoteLine -split "\s+")[0]
if (-not $latestRev) {
    throw "Could not parse basekit revision from: $remoteLine"
}

Write-Host "Latest basekit revision: $latestRev"

$content = Get-Content -Raw -LiteralPath $pyprojectPath
$sourcePattern = '(?m)^basekit\s*=\s*\{.*\}\s*$'
$sourceLine = "basekit = { git = `"$repoUrl`", rev = `"$latestRev`" }"

if ($content -notmatch $sourcePattern) {
    throw "Could not find basekit source entry in $pyprojectPath"
}

$updated = $content -replace $sourcePattern, $sourceLine

if ($DryRun) {
    Write-Host "Dry run: pyproject.toml and uv.lock were not changed."
    Write-Host "Would set:"
    Write-Host "  $sourceLine"
    exit 0
}

[System.IO.File]::WriteAllText(
    $pyprojectPath,
    $updated,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Updated pyproject.toml basekit source:"
Write-Host "  $sourceLine"

Push-Location $repoRoot
try {
    uv lock --upgrade-package basekit
    uv sync
}
finally {
    Pop-Location
}

Write-Host "basekit source and lockfile are updated."
