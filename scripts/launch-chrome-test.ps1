[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot 'runtime'
$extensionRoot = Join-Path $projectRoot 'apps\extension\dist'
$profileRoot = Join-Path $runtimeRoot 'chrome-profile'
$helperScript = Join-Path $projectRoot 'scripts\start-helper.ps1'
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'

if (-not (Test-Path -LiteralPath $chrome)) {
    throw "Không tìm thấy Google Chrome tại $chrome"
}
if (-not (Test-Path -LiteralPath (Join-Path $extensionRoot 'manifest.json'))) {
    throw 'Chưa có extension build. Chạy .\scripts\setup.ps1 trước.'
}

New-Item -ItemType Directory -Force -Path $profileRoot | Out-Null
$listener = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    Start-Process `
        -FilePath 'pwsh.exe' `
        -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $helperScript) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Start-Process `
    -FilePath $chrome `
    -ArgumentList @(
        "--user-data-dir=`"$profileRoot`"",
        "--disable-extensions-except=`"$extensionRoot`"",
        "--load-extension=`"$extensionRoot`"",
        'https://meet.google.com/'
    ) `
    -WorkingDirectory $projectRoot

Write-Host 'Chrome test đã mở. Profile, cache và metadata thử nghiệm nằm trong runtime\chrome-profile trên ổ D.' -ForegroundColor Green
Write-Host 'Sau khi ghi thử, chạy: .\scripts\validate-latest-meeting.ps1'
