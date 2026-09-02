@echo off
rem 共送E プロジェクトルートと PYTHONPATH
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "PYTHONPATH=%ROOT_DIR%\src;%PYTHONPATH%"
if not defined KABURADAR_PAGES_URL set "KABURADAR_PAGES_URL=https://lalakuma.github.io/KabuRadar3"
