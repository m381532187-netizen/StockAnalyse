# Register a daily scheduled task that runs run_batch.py (score + email) at the given times.
# Usage (run in this folder):
#   powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1 -Times 09:30,15:30
# Remove:
#   Unregister-ScheduledTask -TaskName StockAnalyseDaily -Confirm:$false
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as system
# ANSI codepage; non-ASCII without a BOM breaks the parser.
param(
    [string[]]$Times = @("09:30", "15:30"),
    [string]$TaskName = "StockAnalyseDaily"
)

# Normalize: allow "09:30,15:30" passed as one string via -File.
$Times = $Times | ForEach-Object { $_ -split ',' } | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }

$py = (Get-Command python).Source
if (-not $py) { Write-Error "python not found on PATH"; exit 1 }
$root = $PSScriptRoot
$script = Join-Path $root "run_batch.py"

$action = New-ScheduledTaskAction -Execute $py -Argument "`"$script`"" -WorkingDirectory $root
$triggers = @()
foreach ($t in $Times) { $triggers += New-ScheduledTaskTrigger -Daily -At $t }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings -Description "Daily stock bottom score (runs at $($Times -join '/'))" -Force | Out-Null

Write-Host "Registered task '$TaskName' to run daily at $($Times -join ' / ')." -ForegroundColor Green
Write-Host "Check : Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo" -ForegroundColor Gray
Write-Host "Test  : Start-ScheduledTask -TaskName $TaskName" -ForegroundColor Gray
