@echo off
rem 手動: 現在時刻のスロットがあれば1回実行
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\scheduling\launcher.py" --due %*
endlocal & exit /b 0
