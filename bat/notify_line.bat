@echo off
rem LINE 通知（1日1回・16:00 スロット相当）
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\notify_line.py" %*
endlocal & exit /b 0
