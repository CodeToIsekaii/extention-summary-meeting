[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot 'runtime'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:TEMP = Join-Path $runtimeRoot 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $runtimeRoot 'pip-cache'
$env:npm_config_cache = Join-Path $runtimeRoot 'npm-cache'

& $python -m pytest (Join-Path $projectRoot 'apps\helper\tests') --basetemp (Join-Path $runtimeRoot 'pytest-verify')
& $python -m ruff check (Join-Path $projectRoot 'apps\helper')
Push-Location (Join-Path $projectRoot 'apps\extension')
try {
    npm test
    npm run build
} finally {
    Pop-Location
}

$settings = Get-Content -Raw -LiteralPath (Join-Path $projectRoot 'config\settings.json') | ConvertFrom-Json
if (-not ([string]$settings.runtime_root).StartsWith('D:\')) { throw 'runtime_root is not on D:.' }

$parseErrors = @()
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'scripts') -Filter '*.ps1' | ForEach-Object {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $_.FullName,
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null
    if ($errors) { $parseErrors += $errors }
}
if ($parseErrors.Count -gt 0) {
    $parseErrors | Format-List
    throw 'PowerShell syntax verification failed.'
}

$distManifest = Join-Path $projectRoot 'apps\extension\dist\manifest.json'
if (-not (Test-Path -LiteralPath $distManifest)) { throw 'Extension dist manifest is missing.' }
Write-Host 'Verification complete.' -ForegroundColor Green
