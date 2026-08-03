[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot 'runtime'
$meetingsRoot = Join-Path $runtimeRoot 'meetings'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

$meeting = Get-ChildItem -LiteralPath $meetingsRoot -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $meeting) {
    throw 'Chưa có meeting hoàn chỉnh trong runtime\meetings.'
}

$files = @(Get-ChildItem -LiteralPath $meeting.FullName -File | Sort-Object Name)
$names = @($files.Name)
if (($names -join ',') -ne 'minutes.json,recording.webm') {
    throw "Meeting phải chỉ có minutes.json và recording.webm; hiện có: $($names -join ', ')"
}

$minutesPath = Join-Path $meeting.FullName 'minutes.json'
$recordingPath = Join-Path $meeting.FullName 'recording.webm'
$minutes = Get-Content -LiteralPath $minutesPath -Raw | ConvertFrom-Json
if ((Get-Item -LiteralPath $recordingPath).Length -le 0) {
    throw 'recording.webm rỗng.'
}

$missingEvidence = @($minutes.action_items | Where-Object { -not $_.evidence -or $_.evidence.Count -eq 0 })
if ($missingEvidence.Count -gt 0) {
    throw "$($missingEvidence.Count) task không có evidence."
}
$invalidUnknown = @(
    $minutes.action_items |
        Where-Object {
            (-not $_.assignee -or -not $_.deadline) -and $_.status -ne 'needs_confirmation'
        }
)
if ($invalidUnknown.Count -gt 0) {
    throw "$($invalidUnknown.Count) task thiếu owner/deadline nhưng không có trạng thái needs_confirmation."
}

$ffmpeg = & $python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
& $ffmpeg -hide_banner -loglevel error -i $recordingPath -f null 'NUL'
if ($LASTEXITCODE -ne 0) {
    throw 'FFmpeg không giải mã lại được recording.webm.'
}

$workPath = Join-Path (Join-Path $runtimeRoot 'work') ([string]$minutes.meeting_id)
if (Test-Path -LiteralPath $workPath) {
    throw "runtime\work vẫn còn session đã hoàn tất: $($minutes.meeting_id)"
}

[pscustomobject]@{
    Meeting = $meeting.Name
    DurationSeconds = [math]::Round(([double]$minutes.duration_ms / 1000), 1)
    TranscriptSegments = @($minutes.transcript).Count
    Tasks = @($minutes.action_items).Count
    TasksWithEvidence = @($minutes.action_items | Where-Object { $_.evidence.Count -gt 0 }).Count
    RecordingMB = [math]::Round((Get-Item -LiteralPath $recordingPath).Length / 1MB, 2)
    Result = 'PASS'
} | Format-List
