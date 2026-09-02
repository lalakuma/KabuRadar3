@echo off
rem 常駐スケジューラ（launcher --loop）を停止。本番はタスクスケジューラのみ推奨。
setlocal
for /f "tokens=2" %%p in ('wmic process where "CommandLine like '%%launcher.py%%--loop%%'" get ProcessId ^| findstr /r "[0-9]"') do (
  echo Stopping PID %%p
  taskkill /PID %%p /F >nul 2>&1
)
echo Done. Use register_task_scheduler.bat for scheduled runs.
endlocal & exit /b 0
