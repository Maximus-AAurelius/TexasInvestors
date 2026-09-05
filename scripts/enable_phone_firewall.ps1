param([Parameter(Mandatory=$true)][string]$LocalAddress)
$ErrorActionPreference = 'Stop'
$parsedAddress = [System.Net.IPAddress]::Parse($LocalAddress)
if ($parsedAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'Use your private Wi-Fi IPv4 address.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$configuration = Get-Content -LiteralPath (Join-Path $projectRoot 'output/phone/config.json') -Raw | ConvertFrom-Json
if ($configuration.ip -ne $LocalAddress -or $configuration.port -ne 8766) { throw 'Address does not match the configured phone listener.' }
$ruleName = 'TexasInvestors-Phone-HTTPS'
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound -Action Allow -Profile Any
    $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -LocalAddress $LocalAddress -RemoteAddress LocalSubnet
    $existing | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort 8766
} else {
    New-NetFirewallRule -Name $ruleName -DisplayName 'Texas Investors phone HTTPS (local subnet only)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8766 -LocalAddress $LocalAddress -RemoteAddress LocalSubnet -Profile Any | Out-Null
}
Write-Output 'Allowed TCP 8766 only at the configured LAN address, from the local subnet.'
