@echo off
rem 旧 KabuRadar（HI スクリーニング + LINE）のタスクを削除
setlocal
echo 旧 KabuRadar HI タスクを検索して削除します...
python "%~dp0..\scripts\disable_legacy_hi_tasks.py"
endlocal & exit /b 0
