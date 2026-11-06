<#
.SYNOPSIS
    Sakthi Manufacturing MIS Report Generator — PowerShell Task Automation Script
.DESCRIPTION
    Wrapper script for triggering automated weekly or monthly MIS reporting jobs
    via Windows Task Scheduler or manual administrative runs.
.EXAMPLE
    .\run_scheduled_job.ps1 -Job weekly -Period "2026-W45"
    .\run_scheduled_job.ps1 -Job monthly -Period "2026-11"
#>
param (
    [ValidateSet("weekly", "monthly", "all")]
    [string]$Job = "all",

    [string]$Period = ""
)

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Sakthi MIS Report Generator Task Runner" -ForegroundColor Cyan
Write-Host " Job: $Job | Period: $Period" -ForegroundColor Cyan
Write-Host " Working Directory: $RootDir" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ArgsList = @("-m", "scheduler.jobs", "--job", $Job)

if ($Period) {
    if ($Job -eq "monthly") {
        $ArgsList += @("--month", $Period)
    } else {
        $ArgsList += @("--week", $Period)
    }
}

$Process = Start-Process -FilePath "python" -ArgumentList $ArgsList -Wait -NoNewWindow -PassThru
if ($Process.ExitCode -ne 0) {
    Write-Error "Scheduled job failed with exit code $($Process.ExitCode)"
    exit $Process.ExitCode
}

Write-Host "Job completed successfully." -ForegroundColor Green
exit 0

