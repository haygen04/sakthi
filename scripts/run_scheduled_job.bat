@echo off
REM ==============================================================================
REM Sakthi Manufacturing MIS Report Generator — Task Scheduler Fallback Script
REM Usage:
REM   run_scheduled_job.bat weekly [YYYY-Www]
REM   run_scheduled_job.bat monthly [YYYY-MM]
REM ==============================================================================

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

set JOB_TYPE=%1
if "%JOB_TYPE%"=="" set JOB_TYPE=all

set PERIOD_ARG=%2

echo [INFO] Running Sakthi MIS Pipeline: %JOB_TYPE% %PERIOD_ARG%

if "%JOB_TYPE%"=="weekly" (
    if "%PERIOD_ARG%"=="" (
        python -m scheduler.jobs --job weekly
    ) else (
        python -m scheduler.jobs --job weekly --week %PERIOD_ARG%
    )
) else if "%JOB_TYPE%"=="monthly" (
    if "%PERIOD_ARG%"=="" (
        python -m scheduler.jobs --job monthly
    ) else (
        python -m scheduler.jobs --job monthly --month %PERIOD_ARG%
    )
) else (
    python -m scheduler.jobs --job all
)

echo [INFO] Exit code: %ERRORLEVEL%
exit /b %ERRORLEVEL%

