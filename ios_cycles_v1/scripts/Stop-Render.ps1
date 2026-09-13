$ErrorActionPreference = 'Stop'
$taskPackage = Split-Path -Parent $PSScriptRoot
New-Item -ItemType File -Path (Join-Path $taskPackage 'STOP_AFTER_FRAME') -Force | Out-Null
Write-Output 'Pause requested. The current Cycles frame is saved before the worker exits.'
