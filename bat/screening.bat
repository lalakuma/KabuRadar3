@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
call "%~dp0update_prices.bat" --menu auto || exit /b 1
call "%~dp0analyze.bat" || exit /b 1
echo Completed: screening.bat
endlocal & exit /b 0
