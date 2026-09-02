@echo off
rem タスクスケジューラ用: 指定スロットを1回実行（例: lo_1130）
setlocal
if "%~1"=="" (
  echo Usage: run_slot_once.bat SLOT_ID
  echo   lo_1130 / lo_1500 / lo_1600
  exit /b 1
)
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\src\kaburadar3\scheduling\launcher.py" --once %1 || exit /b 1
endlocal & exit /b 0
