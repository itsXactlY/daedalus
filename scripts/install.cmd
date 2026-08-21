@echo off
REM ============================================================================
REM Daedalus Agent Installer for Windows (CMD wrapper)
REM ============================================================================
REM This batch file launches the PowerShell installer for users running CMD.
REM
REM Usage:
REM   curl -fsSL <YOUR_DAEDALUS_REPO_RAW_URL>/scripts/install.cmd -o install.cmd && install.cmd && del install.cmd
REM
REM Or if you're already in PowerShell, use the direct command instead:
REM   irm <YOUR_DAEDALUS_REPO_RAW_URL>/scripts/install.ps1 | iex
REM ============================================================================

echo.
echo  Daedalus Agent Installer
echo  Launching PowerShell installer...
echo.

powershell -ExecutionPolicy ByPass -NoProfile -Command "irm <YOUR_DAEDALUS_REPO_RAW_URL>/scripts/install.ps1 | iex"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Installation failed. Please try running PowerShell directly:
    echo    powershell -ExecutionPolicy ByPass -c "irm <YOUR_DAEDALUS_REPO_RAW_URL>/scripts/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)
