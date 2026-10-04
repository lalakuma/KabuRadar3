@echo off
rem Windows タスクスケジューラに KabuRadar3 を登録（取りこぼし防止設定付き）
rem 平日 11:30 / 15:00 / 16:00 LO + 15分ごとの未実行補完（〜19:00）
setlocal
set "ROOT=%~dp0.."
set "RUN=%ROOT%\bat\run_slot_once.bat"
set "DUE=%ROOT%\bat\run_due_catchup.bat"
set "PS1=%ROOT%\bat\harden_task_scheduler.ps1"

schtasks /Delete /TN "KabuRadar3-HI-1130" /F 2>nul
schtasks /Create /TN "KabuRadar3-LO-1130" /TR "cmd /c \"\"%RUN%\" lo_1130\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:30 /F || exit /b 1
schtasks /Create /TN "KabuRadar3-LO-1500" /TR "cmd /c \"\"%RUN%\" lo_1500\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:00 /F || exit /b 1
schtasks /Create /TN "KabuRadar3-LO-1600" /TR "cmd /c \"\"%RUN%\" lo_1600\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:00 /F || exit /b 1

rem 取りこぼし補完: 平日 11:45〜19:00 の15分ごと（既実行はスキップ）
schtasks /Delete /TN "KabuRadar3-LO-CATCHUP" /F 2>nul
schtasks /Create /TN "KabuRadar3-LO-CATCHUP" /TR "cmd /c \"\"%DUE%\"\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:45 /F || exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" || exit /b 1

echo.
echo Registered (hardened):
powershell -NoProfile -Command ^
  "Get-ScheduledTask -TaskName 'KabuRadar3-*' | ForEach-Object { $i=Get-ScheduledTaskInfo $_; '{0}  Last={1}  Next={2}  Wake={3}  Missed={4}' -f $_.TaskName,$i.LastRunTime,$i.NextRunTime,$_.Settings.WakeToRun,$_.Settings.StartWhenAvailable }"
endlocal & exit /b 0
