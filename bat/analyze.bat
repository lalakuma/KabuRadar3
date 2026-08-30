@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\analyze.py" %* || exit /b 1
echo Completed: analyze.bat
endlocal & exit /b 0
