[CmdletBinding()]
param(
    [string]$TaskName = "PhotoStockService Autostart",

    [ValidateRange(0, 600)]
    [int]$DelaySeconds = 60
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$startupScript = Join-Path $PSScriptRoot "start-photostock.ps1"
$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $startupScript)) {
    throw "Startup script was not found: $startupScript"
}
if (-not (Test-Path -LiteralPath $dockerDesktop)) {
    throw "Docker Desktop was not found: $dockerDesktop"
}

New-ItemProperty `
    -Path $runKey `
    -Name "Docker Desktop" `
    -Value "`"$dockerDesktop`"" `
    -PropertyType String `
    -Force | Out-Null

$powerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$startupScript`""

$action = New-ScheduledTaskAction `
    -Execute $powerShellExe `
    -Argument $arguments `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
if ($DelaySeconds -gt 0) {
    $trigger.Delay = "PT${DelaySeconds}S"
}

$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Starts Docker Desktop and PhotoStockService with eight Celery workers after user logon." `
    -Force | Out-Null

Write-Host "Docker Desktop autostart enabled."
Write-Host "Scheduled task registered: $TaskName"
Write-Host "Startup script: $startupScript"
