@echo off
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\scheduler\launcher.py" %* || exit /b 1
endlocal & exit /b 0
