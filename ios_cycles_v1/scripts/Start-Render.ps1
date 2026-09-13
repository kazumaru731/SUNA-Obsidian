param(
    [ValidateSet('pilot', 'full')][string]$Stage = 'full',
    [string]$Python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)
$ErrorActionPreference = 'Stop'
$taskPackage = Split-Path -Parent $PSScriptRoot
$taskRunner = Join-Path $PSScriptRoot 'run_batch.py'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
if (Test-Path -LiteralPath (Join-Path $taskPackage 'STOP_AFTER_FRAME')) { throw 'Paused. Use Resume-Render.ps1 to resume.' }
$taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$taskOut = Join-Path $taskPackage "checks\controller_$taskStamp.log"
$taskErr = Join-Path $taskPackage "checks\controller_$taskStamp.error.log"
$taskProcess = Start-Process -FilePath $Python -ArgumentList @('-u', ('"' + $taskRunner + '"'), '--stage', $Stage) -WorkingDirectory $taskPackage -WindowStyle Hidden -RedirectStandardOutput $taskOut -RedirectStandardError $taskErr -PassThru
Write-Output "Started controller PID $($taskProcess.Id). Status: $taskPackage\checks\batch_status.json"
Write-Output "Log: $taskOut"
