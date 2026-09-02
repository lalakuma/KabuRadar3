@echo off
rem Windows タスクスケジューラに KabuRadar3 を登録（平日 11:30 / 15:00 / 16:00 LO）
setlocal
set "ROOT=%~dp0.."
set "RUN=%ROOT%\bat\run_slot_once.bat"

schtasks /Delete /TN "KabuRadar3-HI-1130" /F 2>nul
schtasks /Create /TN "KabuRadar3-LO-1130" /TR "cmd /c \"\"%RUN%\" lo_1130\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:30 /F || exit /b 1
schtasks /Create /TN "KabuRadar3-LO-1500" /TR "cmd /c \"\"%RUN%\" lo_1500\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:00 /F || exit /b 1
schtasks /Create /TN "KabuRadar3-LO-1600" /TR "cmd /c \"\"%RUN%\" lo_1600\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:00 /F || exit /b 1

echo.
echo Registered:
schtasks /Query /TN "KabuRadar3-LO-1130" /FO LIST /V | findstr /I "TaskName Next Run Time Status"
schtasks /Query /TN "KabuRadar3-LO-1500" /FO LIST /V | findstr /I "TaskName Next Run Time Status"
schtasks /Query /TN "KabuRadar3-LO-1600" /FO LIST /V | findstr /I "TaskName Next Run Time Status"
endlocal & exit /b 0
