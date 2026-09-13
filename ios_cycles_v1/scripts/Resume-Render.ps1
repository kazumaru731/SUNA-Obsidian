param([ValidateSet('pilot', 'full')][string]$Stage = 'full')
$ErrorActionPreference = 'Stop'
$taskPackage = Split-Path -Parent $PSScriptRoot
$taskStatusPath = Join-Path $taskPackage 'checks\batch_status.json'
if (Test-Path -LiteralPath $taskStatusPath) {
    $taskStatus = Get-Content -LiteralPath $taskStatusPath -Raw | ConvertFrom-Json
    foreach ($taskPid in @($taskStatus.pid, $taskStatus.workerPID)) {
        if ($taskPid -and (Get-Process -Id $taskPid -ErrorAction SilentlyContinue)) {
            throw "Process $taskPid may still be active. Wait for the paused status and process exit before resuming."
        }
    }
}
$taskStopFile = Join-Path $taskPackage 'STOP_AFTER_FRAME'
if (Test-Path -LiteralPath $taskStopFile) { Remove-Item -LiteralPath $taskStopFile }
& (Join-Path $PSScriptRoot 'Start-Render.ps1') -Stage $Stage
