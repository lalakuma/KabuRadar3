@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\publish.py" %* || exit /b 1
echo Completed: publish.bat
endlocal & exit /b 0
