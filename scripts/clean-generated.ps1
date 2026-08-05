[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$IncludeBuildOutput,
    [switch]$IncludePythonCaches
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# This script never touches runtime\models, runtime\meetings or runtime\work.
$targets = @(
    (Join-Path $projectRoot 'apps\extension\node_modules'),
    (Join-Path $projectRoot 'apps\extension\.pytest_cache'),
    (Join-Path $projectRoot 'apps\helper\.pytest_cache'),
    (Join-Path $projectRoot 'apps\helper\.ruff_cache'),
    (Join-Path $projectRoot '.ruff_cache')
)
if ($IncludeBuildOutput) { $targets += (Join-Path $projectRoot 'apps\extension\dist') }
if ($IncludePythonCaches) {
    $targets += Get-ChildItem -Path $projectRoot -Directory -Recurse -Force -Filter '__pycache__' |
        Where-Object { $_.FullName -notlike '*\.venv\*' } |
        Select-Object -ExpandProperty FullName
}

foreach ($target in $targets | Select-Object -Unique) {
    if (Test-Path -LiteralPath $target) {
        if ($PSCmdlet.ShouldProcess($target, 'Remove generated cache')) {
            Remove-Item -LiteralPath $target -Recurse -Force
            Write-Output "Removed $target"
        }
    }
}

Write-Output 'Kept runtime\models, runtime\meetings, runtime\work, runtime\logs and config\settings.json.'
