# Deploy the API to Railway from a clean snapshot of the committed code.
# Usage (after `railway login` once):  powershell -ExecutionPolicy Bypass -File deploy_server.ps1
# Uses git archive so the local .venv, dist and vault never leave this PC.
$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$stage  = Join-Path $env:TEMP "epu_deploy_src"
$zip    = "$stage.zip"
$projectId = "828d8b82-3276-4038-8ba4-0a425b6e2dc2"
$envId     = "4e08566c-5d7b-4b22-8236-9591985f09ec"
$svcName   = "epu-api"

Set-Location $root
Remove-Item $zip, $stage -Recurse -Force -ErrorAction SilentlyContinue
git archive --format=zip -o $zip HEAD
Expand-Archive -Path $zip -DestinationPath $stage -Force

Set-Location $stage
railway link -p $projectId -e production -s $svcName | Out-Null
railway up --detach --service $svcName
Write-Host "Deploy submitted. Check status with: railway status"
