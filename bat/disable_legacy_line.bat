@echo off
rem 旧 KabuRadar の LINE 通知（HI/LO・★なし）を止める
setlocal
call "%~dp0_env.bat" || exit /b 1
python "%ROOT_DIR%\scripts\disable_legacy_line.py"
endlocal & exit /b 0
