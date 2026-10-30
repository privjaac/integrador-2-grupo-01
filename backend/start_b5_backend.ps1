$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$python = Join-Path $backendRoot 'venv\Scripts\python.exe'
$portCheck = [System.Net.Sockets.TcpClient]::new()
try {
    $pending = $portCheck.ConnectAsync('127.0.0.1', 8001)
    if ($pending.Wait(500) -and $portCheck.Connected) {
        throw 'El puerto 8001 ya está ocupado; no se iniciará otra instancia del backend.'
    }
}
finally {
    $portCheck.Dispose()
}

Set-Location -LiteralPath $backendRoot
$pythonEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $pythonEncoding
$env:PYTHONIOENCODING = 'utf-8'
& $python '.\start_b5_backend.py'
if ($LASTEXITCODE -ne 0) {
    throw "El backend B5 terminó con código $LASTEXITCODE."
}
