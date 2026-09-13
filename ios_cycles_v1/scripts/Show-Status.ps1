$ErrorActionPreference = 'Stop'
$taskPackage = Split-Path -Parent $PSScriptRoot
$taskBatch = Join-Path $taskPackage 'checks\batch_status.json'
$taskWorker = Join-Path $taskPackage 'checks\worker_status.json'
$taskManifest = Join-Path $taskPackage 'manifest.json'
if (Test-Path -LiteralPath $taskBatch) {
    $taskState = Get-Content -LiteralPath $taskBatch -Raw | ConvertFrom-Json
    Write-Output ("Batch: {0} | updated UTC: {1}" -f $taskState.status, $taskState.updatedUTC)
    if ($taskState.error) { Write-Output ("Error: " + $taskState.error) }
    if ($taskState.measurements) {
        Write-Output ("PNG frames: {0} / {1}" -f $taskState.measurements.renderedMasterFrames, $taskState.measurements.expectedMasterFrames)
        Write-Output ("Remaining render estimate: {0:N1} hours (plus encoding/checks)" -f $taskState.measurements.remainingRenderHoursEstimate)
    }
}
if (Test-Path -LiteralPath $taskWorker) {
    $taskFrame = Get-Content -LiteralPath $taskWorker -Raw | ConvertFrom-Json
    Write-Output ("Worker: {0} | remaining: {1}% | phase frame: {2}" -f $taskFrame.status, $taskFrame.remaining, $taskFrame.frame)
}
if (Test-Path -LiteralPath $taskManifest) {
    $taskAssets = Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
    Write-Output ("Validated videos: {0} / 101 | delivery: {1}" -f $taskAssets.validatedClipCount, $taskAssets.status)
}
$taskCompletion = Join-Path $taskPackage 'checks\completion.json'
if (Test-Path -LiteralPath $taskCompletion) {
    $taskDone = Get-Content -LiteralPath $taskCompletion -Raw | ConvertFrom-Json
    Write-Output ("Completed package: " + $taskDone.archive)
    Write-Output ("SHA-256: " + $taskDone.archiveSha256)
}
