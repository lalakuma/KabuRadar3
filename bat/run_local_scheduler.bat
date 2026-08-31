@echo off
rem ローカル常駐スケジューラ（11:30 HI / 15:00 LO / 16:00 LO）
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\scheduling\launcher.py" --loop --interval 30 %*
endlocal & exit /b 0
