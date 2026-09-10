$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root "server\.venv\Scripts\python.exe"
$npm = Join-Path $env:ProgramFiles "nodejs\npm.cmd"
if (-not (Test-Path $npm)) {
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npmCmd) { $npm = $npmCmd.Source }
}

function Test-LocalPort([int]$Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $Port)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Path $python)) {
    Write-Host "Backend venv ontbreekt. Eenmalig:"
    Write-Host "  cd server"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

if (-not $npm -or -not (Test-Path $npm)) {
    Write-Host "npm.cmd niet gevonden. Installeer Node.js en probeer opnieuw."
    exit 1
}

if (-not (Test-LocalPort 8000)) {
    $backendCmd = @"
Set-Location '$root\server'
Write-Host 'Pixelator backend  http://127.0.0.1:8000' -ForegroundColor Cyan
& '$python' -m uvicorn app:app --reload --reload-exclude '.venv' --host 127.0.0.1 --port 8000
"@
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backendCmd)
} else {
    Write-Host "Backend draait al op http://127.0.0.1:8000"
}

$frontendPorts = @(5173, 5174, 5175)
$frontendUp = $frontendPorts | Where-Object { Test-LocalPort $_ } | Select-Object -First 1
if (-not $frontendUp) {
    $frontendCmd = @"
Set-Location '$root\client'
Write-Host 'Pixelator frontend  http://localhost:5173' -ForegroundColor Green
& '$npm' run dev
"@
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCmd)
}

$ready = $null
foreach ($i in 1..30) {
    Start-Sleep -Milliseconds 400
    $ready = $frontendPorts | Where-Object { Test-LocalPort $_ } | Select-Object -First 1
    if ($ready) { break }
}

if ($ready) {
    Write-Host ""
    Write-Host "Open de app hier: http://localhost:$ready/" -ForegroundColor Green
    Write-Host "Niet http://localhost:8000 — dat is alleen de API."
} else {
    Write-Host "Frontend startte niet. Kijk in het groene frontend-venster naar de fout."
    exit 1
}
