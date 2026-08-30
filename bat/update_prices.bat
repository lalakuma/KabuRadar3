@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\update_prices.py" %* || exit /b 1
echo Completed: update_prices.bat
endlocal & exit /b 0
