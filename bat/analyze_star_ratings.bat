@echo off
rem 星評価（★1-5）の予測力バックテスト
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\scripts\analyze_star_ratings.py" %*
endlocal & exit /b 0
