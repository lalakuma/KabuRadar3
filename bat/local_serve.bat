@echo off
rem docs/ をローカル HTTP で表示（data.json 確認用）
setlocal
call "%~dp0_env.bat" || exit /b 1
echo Open http://127.0.0.1:8080/ in browser
python -m http.server 8080 --directory "%ROOT_DIR%\docs"
endlocal & exit /b 0
