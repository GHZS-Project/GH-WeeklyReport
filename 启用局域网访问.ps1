$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$ruleName = "周报分析局域网 8787"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  exit
}
if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) { Remove-NetFirewallRule -DisplayName $ruleName }
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 8787 -Action Allow -Profile Private
Write-Host "已允许局域网访问 8787 端口，请按任意键关闭。" -ForegroundColor Green
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
