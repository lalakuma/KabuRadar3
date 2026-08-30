@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
call "%~dp0update_prices.bat" --menu 6 || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\screening.py" --skip-update --notify || exit /b 1
echo Completed: screening_notify.bat
endlocal & exit /b 0
