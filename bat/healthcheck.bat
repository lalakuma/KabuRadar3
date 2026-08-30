@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\healthcheck.py" --require-db %* || exit /b 1
echo Completed: healthcheck.bat
endlocal & exit /b 0
