param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$Backend = Join-Path $Root "web\backend"
$Logs = if ($env:NANODLNA_LOG_DIR) { $env:NANODLNA_LOG_DIR } else { Join-Path $Root "logs" }
$Port = if ($env:NANODLNA_BACKEND_PORT) { $env:NANODLNA_BACKEND_PORT } else { "8088" }

$pythonCandidates = @()
if ($env:NANODLNA_PYTHON_BIN) {
    $pythonCandidates += $env:NANODLNA_PYTHON_BIN
}
$pythonCandidates += @(
    (Join-Path $Root ".conda-walldisplay\python.exe"),
    (Join-Path $Root ".venv\Scripts\python.exe"),
    "python"
)

$Python = $pythonCandidates | Where-Object { $_ -eq "python" -or (Test-Path $_) } | Select-Object -First 1
if (-not $Python) {
    throw "No Python runtime found. Set NANODLNA_PYTHON_BIN or create .conda-walldisplay/.venv."
}

New-Item -ItemType Directory -Force $Logs | Out-Null

function Get-WallDisplayLanIp {
    try {
        $ipConfig = Get-NetIPConfiguration -ErrorAction Stop |
            Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
            Select-Object -First 1
        if ($ipConfig -and $ipConfig.IPv4Address.IPAddress) {
            return $ipConfig.IPv4Address.IPAddress
        }
    } catch {
        # Non-admin scheduled/user shells can be denied CIM access.
    }

    try {
        $netIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -notlike "169.254.*" -and
                $_.IPAddress -ne "127.0.0.1" -and
                $_.PrefixOrigin -ne "WellKnown"
            } |
            Select-Object -First 1 -ExpandProperty IPAddress
        if ($netIp) {
            return $netIp
        }
    } catch {
        # Keep startup working even when NetTCPIP cmdlets are unavailable.
    }

    try {
        $dnsIp = [System.Net.Dns]::GetHostEntry([System.Net.Dns]::GetHostName()).AddressList |
            Where-Object {
                $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
                $_.IPAddressToString -notlike "169.254.*" -and
                $_.IPAddressToString -ne "127.0.0.1"
            } |
            Select-Object -First 1
        if ($dnsIp) {
            return $dnsIp.IPAddressToString
        }
    } catch {
    }

    return "127.0.0.1"
}

$lanIp = Get-WallDisplayLanIp
$DatabasePath = Join-Path $Backend "nanodlna.db"
$DatabaseUrlPath = $DatabasePath -replace "\\", "/"

$env:PYTHONPATH = "$Root;$Backend"
$env:PYTHONIOENCODING = "utf-8"
$env:NANODLNA_HOST = "0.0.0.0"
$env:NANODLNA_BACKEND_PORT = $Port
$env:NANODLNA_SERVER_BASE_URL = "http://$lanIp`:$Port"
$env:NANODLNA_LOG_DIR = $Logs
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite:///$DatabaseUrlPath"
}

$healthUrl = "http://127.0.0.1:$Port/health"
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
        "WallDisplay is already responding at $healthUrl" |
            Out-File -FilePath (Join-Path $Logs "backend-console.log") -Append -Encoding utf8
        exit 0
    }
} catch {
    # Expected when the backend is not already running.
}

$runPy = Join-Path $Backend "run.py"
$logFile = Join-Path $Logs "backend-console.log"

"Starting WallDisplay at $(Get-Date -Format o)" | Out-File -FilePath $logFile -Append -Encoding utf8
"LAN URL: http://$lanIp`:$Port/app" | Out-File -FilePath $logFile -Append -Encoding utf8
"Database URL: $($env:DATABASE_URL)" | Out-File -FilePath $logFile -Append -Encoding utf8

if ($Detached) {
    $command = "chcp 65001 > nul && `"$Python`" `"$runPy`" --host 0.0.0.0 --port $Port >> `"$logFile`" 2>&1"
    $launcher = Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList @("/d", "/c", $command) `
        -WorkingDirectory $Backend `
        -WindowStyle Hidden `
        -PassThru

    "Started detached backend launcher PID: $($launcher.Id)" | Out-File -FilePath $logFile -Append -Encoding utf8
    exit 0
}

"Running backend in foreground for scheduler/service ownership" | Out-File -FilePath $logFile -Append -Encoding utf8
& $Python $runPy --host 0.0.0.0 --port $Port
exit $LASTEXITCODE
