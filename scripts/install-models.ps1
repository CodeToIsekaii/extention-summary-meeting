[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot 'runtime'
$modelsRoot = Join-Path $runtimeRoot 'models'
$tmpRoot = Join-Path $runtimeRoot 'tmp'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Run .\scripts\setup.ps1 first.'
}

New-Item -ItemType Directory -Force -Path $modelsRoot,$tmpRoot | Out-Null
$env:TEMP = $tmpRoot
$env:TMP = $tmpRoot
$env:HF_HOME = Join-Path $runtimeRoot 'cache\huggingface'
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:XDG_CACHE_HOME = Join-Path $runtimeRoot 'cache'
$env:HF_HUB_DISABLE_XET = '1'

& $venvPython (Join-Path $PSScriptRoot 'install_models.py') --runtime $runtimeRoot

$qwenModel = Join-Path $modelsRoot 'Qwen3-4B-Q5_K_M.gguf'
if (-not (Test-Path -LiteralPath $qwenModel) -or (Get-Item -LiteralPath $qwenModel).Length -lt 2800000000) {
    Write-Host 'Downloading Qwen3 4B Q5_K_M with resumable HTTP (about 2.7 GB)...'
    $qwenUrl = 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q5_K_M.gguf?download=true'
    & curl.exe -L --fail --retry 5 --retry-delay 5 -C - --output $qwenModel $qwenUrl
    if ($LASTEXITCODE -ne 0) { throw "Qwen download failed with exit code $LASTEXITCODE" }
}

$llamaRoot = Join-Path $modelsRoot 'llama.cpp'
$llamaCli = Join-Path $llamaRoot 'llama-cli.exe'
if (-not (Test-Path -LiteralPath $llamaCli)) {
    Write-Host 'Downloading official llama.cpp Windows CPU build...'
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'
    $asset = $release.assets | Where-Object { $_.name -match '^llama-.*-bin-win-cpu-x64\.zip$' } | Select-Object -First 1
    if (-not $asset) { throw 'No Windows x64 CPU llama.cpp asset found in latest release.' }
    $archive = Join-Path $tmpRoot $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archive
    New-Item -ItemType Directory -Force -Path $llamaRoot | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $llamaRoot -Force
    Remove-Item -LiteralPath $archive -Force
}

$required = @(
    (Join-Path $modelsRoot 'faster-whisper-medium\model.bin'),
    $qwenModel,
    $llamaCli
)
$missing = $required | Where-Object { -not (Test-Path -LiteralPath $_) }
if ($missing) { throw "Model installation incomplete: $($missing -join ', ')" }

$modelCaches = @(
    (Join-Path $modelsRoot '.cache'),
    (Join-Path $modelsRoot 'faster-whisper-medium\.cache')
)
foreach ($cache in $modelCaches) {
    if ((Test-Path -LiteralPath $cache) -and (Resolve-Path $cache).Path.StartsWith($modelsRoot)) {
        Remove-Item -LiteralPath $cache -Recurse -Force
    }
}

Write-Host 'Whisper, Qwen và llama.cpp đã sẵn sàng trên ổ D.' -ForegroundColor Green
