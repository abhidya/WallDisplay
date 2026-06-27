$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$BackendRun = Join-Path $Root "web\backend\run.py"
$TaskName = if ($env:WALLDISPLAY_TASK_NAME) { $env:WALLDISPLAY_TASK_NAME } else { "WallDisplay" }
$Port = if ($env:NANODLNA_BACKEND_PORT) { $env:NANODLNA_BACKEND_PORT } else { "8088" }
$BaseUrl = "http://127.0.0.1:$Port"

try {
    $body = @{ projector = "proj-hdmi-local" } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/renderer/stop" -ContentType "application/json" -Body $body -TimeoutSec 5 | Out-Null
    Write-Output "Requested HDMI projector stop."
} catch {
    Write-Output "Projector stop request skipped: $($_.Exception.Message)"
}

try {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
} catch {
    # Task may not exist or may already be stopped.
}

function Stop-ProcessListQuietly {
    param($Processes)

    foreach ($process in $Processes) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$processes = @(Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like "*$BackendRun*"
    })

$projectorBrowsers = @(Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like "*walldisplay_hdmi_*"
    })

Stop-ProcessListQuietly -Processes $processes
Stop-ProcessListQuietly -Processes $projectorBrowsers

if (-not $processes) {
    Write-Output "No WallDisplay backend process found."
} else {
    Write-Output "Stopped WallDisplay backend process(es): $($processes.ProcessId -join ', ')"
}

if ($projectorBrowsers) {
    Write-Output "Stopped HDMI projector browser process(es): $($projectorBrowsers.ProcessId -join ', ')"
}
