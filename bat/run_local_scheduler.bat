@echo off
rem [非推奨] 常駐ループ。本番は register_task_scheduler.bat のみ使ってください（二重実行防止）。
echo WARNING: run_local_scheduler.bat is deprecated. Use Windows Task Scheduler instead.
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\scheduling\launcher.py" --loop --interval 30 %*
endlocal & exit /b 0
