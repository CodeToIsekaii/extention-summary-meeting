[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run .\scripts\setup.ps1 first.' }
$env:PYTHONPATH = Join-Path $projectRoot 'apps\helper\src'
$env:TEMP = Join-Path $projectRoot 'runtime\tmp'
$env:TMP = $env:TEMP
$env:HF_HOME = Join-Path $projectRoot 'runtime\cache\huggingface'
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
& $python (Join-Path $projectRoot 'apps\desktop\main.py')
