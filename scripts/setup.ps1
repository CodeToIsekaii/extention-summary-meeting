[CmdletBinding()]
param(
    [switch]$SkipNpm,
    [switch]$SkipAiDependencies
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot 'runtime'
$configPath = Join-Path $projectRoot 'config\settings.json'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if ([System.IO.Path]::GetPathRoot($projectRoot) -ne 'D:\') {
    throw "Project must remain on D:. Current path: $projectRoot"
}

$runtimeDirectories = @(
    $runtimeRoot,
    (Join-Path $runtimeRoot 'models'),
    (Join-Path $runtimeRoot 'meetings'),
    (Join-Path $runtimeRoot 'work'),
    (Join-Path $runtimeRoot 'logs'),
    (Join-Path $runtimeRoot 'tmp'),
    (Join-Path $runtimeRoot 'cache'),
    (Join-Path $runtimeRoot 'pip-cache'),
    (Join-Path $runtimeRoot 'npm-cache')
)
New-Item -ItemType Directory -Force -Path $runtimeDirectories | Out-Null

if (-not (Test-Path -LiteralPath $configPath)) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $token = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
    $settings = [ordered]@{
        runtime_root = $runtimeRoot
        helper_host = '127.0.0.1'
        helper_port = 8765
        auth_token = $token
        minimum_start_free_gb = 5
        warning_free_gb = 3
        stop_free_gb = 1
        buffer_seconds = 30
        meeting_cpu_percent = 25
        postprocess_cpu_percent = 50
        max_memory_gb = 4
        whisper_model = 'faster-whisper-medium'
        whisper_device = 'cpu'
        whisper_compute_type = 'int8'
        summary_model_file = 'Qwen3-4B-Q5_K_M.gguf'
        language = 'vi'
    }
    $settings | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
}

$env:TEMP = Join-Path $runtimeRoot 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $runtimeRoot 'pip-cache'
$env:npm_config_cache = Join-Path $runtimeRoot 'npm-cache'
$env:HF_HOME = Join-Path $runtimeRoot 'cache\huggingface'
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:XDG_CACHE_HOME = Join-Path $runtimeRoot 'cache'

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv (Join-Path $projectRoot '.venv')
}

& $venvPython -m pip install --upgrade pip
$helperExtras = if ($SkipAiDependencies) { 'dev' } else { 'dev,ai' }
& $venvPython -m pip install -e "$projectRoot\apps\helper[$helperExtras]"

if (-not $SkipNpm) {
    Push-Location (Join-Path $projectRoot 'apps\extension')
    try {
        npm install
        npm run build
    } finally {
        Pop-Location
    }
}

$saved = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
Write-Host ''
Write-Host 'Setup hoàn tất trên ổ D.' -ForegroundColor Green
Write-Host "Token để dán vào extension: $($saved.auth_token)" -ForegroundColor Cyan
Write-Host "Bước tiếp theo: .\scripts\install-models.ps1"
