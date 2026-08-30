@echo off
rem 共送E プロジェクトルートと PYTHONPATH
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "PYTHONPATH=%ROOT_DIR%\src;%PYTHONPATH%"
