@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\analyze.py" --publish %* || exit /b 1
echo Completed: analyze_and_publish.bat
endlocal & exit /b 0
