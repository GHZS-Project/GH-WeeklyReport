param([switch]$RefreshOnly)
$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$url = "http://localhost:8787/"
$health = "http://localhost:8787/api/health"
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node) { throw "未找到 Node.js，请先安装 Node.js" }

if (-not (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $node -ArgumentList "server/server.mjs" -WorkingDirectory $project -WindowStyle Hidden
}

$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-RestMethod $health -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw "周报服务启动超时" }

$status = Invoke-RestMethod "http://localhost:8787/api/status"
Write-Host "周报服务已启动" -ForegroundColor Green
Write-Host "读取目录：$($status.sourceDir)"
Write-Host "局域网地址：$($status.lanUrls -join ' | ')" -ForegroundColor Cyan
if (-not $RefreshOnly) { Start-Process $url }
