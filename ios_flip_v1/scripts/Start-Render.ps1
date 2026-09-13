param(
    [string]$Blender = 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe',
    [ValidateRange(0,30)][int[]]$Frames = (0..30),
    [switch]$Preview,
    [switch]$Icon
)
$ErrorActionPreference = 'Stop'
$taskPackage = Split-Path -Parent $PSScriptRoot
$taskProject = Split-Path -Parent $taskPackage
if (-not (Test-Path -LiteralPath $Blender)) { throw "Blender not found: $Blender" }
if (Test-Path -LiteralPath (Join-Path $taskPackage 'STOP_AFTER_FRAME')) {
    throw 'Paused. Remove STOP_AFTER_FRAME only when you intend to resume.'
}
if (Get-Process -Name blender -ErrorAction SilentlyContinue) {
    throw 'A Blender process is running. Check that it has finished before starting another render.'
}
$taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$taskOut = Join-Path $taskPackage "checks\render_$taskStamp.log"
$taskErr = Join-Path $taskPackage "checks\render_$taskStamp.error.log"
$taskScript = Join-Path $PSScriptRoot 'render_flip.py'
$taskArguments = @('--background','--factory-startup','--python-exit-code','1','--python',('"' + $taskScript + '"'),'--','--frames',($Frames -join ','))
if ($Preview) { $taskArguments += '--preview' }
if ($Icon) { $taskArguments += '--icon' }
$taskProcess = Start-Process -FilePath $Blender -ArgumentList $taskArguments -WorkingDirectory $taskProject -WindowStyle Hidden -RedirectStandardOutput $taskOut -RedirectStandardError $taskErr -PassThru
[pscustomobject]@{ PID = $taskProcess.Id; Log = $taskOut; ErrorLog = $taskErr } | ConvertTo-Json
