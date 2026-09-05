@echo off
rem LINE 通知（スロット単位・1日最大3通 / 手動は --force）
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\notify_line.py" %*
endlocal & exit /b 0
