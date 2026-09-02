@echo off
rem LO: 株価更新 -> 解析(RSI+RCI) -> Web JSON 生成 -> LINE
setlocal
call "%~dp0_env.bat" || exit /b 1
set "KABURADAR_CONFIG=config\config_lo.ini"
python "%ROOT_DIR%\src\kaburadar3\cli\update_prices.py" --menu 6 || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\cli\analyze.py" --config config\config_lo.ini || exit /b 1
call "%~dp0publish.bat" || exit /b 1
if /I "%~1"=="--notify" (
  python "%ROOT_DIR%\src\kaburadar3\cli\notify_line.py" %2 %3 %4 %5 || exit /b 1
)
echo Completed: screening_lo.bat
endlocal & exit /b 0
