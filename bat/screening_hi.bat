@echo off
rem 11:30 HI: 株価更新 -> 解析(RSI+RCI) -> Web JSON 生成 -> LINE
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\update_prices.py" --menu 6 || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\analyze.py" --config config\config_hi.ini || exit /b 1
call "%~dp0publish.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\notify_line.py" || exit /b 1
echo Completed: screening_hi.bat
endlocal & exit /b 0
