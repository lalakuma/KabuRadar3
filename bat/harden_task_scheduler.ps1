# KabuRadar3 タスクの取りこぼし防止設定を適用する。
$ErrorActionPreference = "Stop"

function Set-KabuHardening {
    param([Parameter(Mandatory = $true)][string]$TaskName)

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $settings = $task.Settings
    $settings.WakeToRun = $true
    $settings.StartWhenAvailable = $true
    $settings.DisallowStartIfOnBatteries = $false
    $settings.StopIfGoingOnBatteries = $false
    $settings.AllowHardTerminate = $true
    $settings.ExecutionTimeLimit = "PT2H"
    Set-ScheduledTask -TaskName $TaskName -Settings $settings | Out-Null
    Write-Host "Hardened: $TaskName"
}

foreach ($name in @("KabuRadar3-LO-1130", "KabuRadar3-LO-1500", "KabuRadar3-LO-1600")) {
    Set-KabuHardening -TaskName $name
}

# CATCHUP: 平日 11:45 から 15 分間隔・7時間15分（〜19:00）
$dueBat = Join-Path $PSScriptRoot "run_due_catchup.bat"
$tr = "cmd /c `"\`"$dueBat\`"`""
schtasks /Delete /TN "KabuRadar3-LO-CATCHUP" /F 2>$null | Out-Null
schtasks /Create /TN "KabuRadar3-LO-CATCHUP" /TR $tr /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:45 /RI 15 /DU 07:15 /F | Out-Null
Set-KabuHardening -TaskName "KabuRadar3-LO-CATCHUP"
Write-Host "Catchup: every 15m from 11:45 (~until 19:00)"
Write-Host "Done."
