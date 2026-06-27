$ErrorActionPreference = "Stop"

$Port = if ($env:NANODLNA_BACKEND_PORT) { $env:NANODLNA_BACKEND_PORT } else { "8088" }
$RuleName = if ($env:WALLDISPLAY_FIREWALL_RULE) { $env:WALLDISPLAY_FIREWALL_RULE } else { "WallDisplay Backend $Port" }

$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Firewall rule already exists: $RuleName"
    return
}

New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -Profile Private
