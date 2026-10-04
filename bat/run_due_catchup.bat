@echo off
rem タスクスケジューラ用: 未実行スロットを補完（launcher --due）
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\scheduling\launcher.py" --due || exit /b 1
endlocal & exit /b 0
