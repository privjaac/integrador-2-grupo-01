$ErrorActionPreference = 'Stop'
$frontendRoot = $PSScriptRoot
$portCheck = [System.Net.Sockets.TcpClient]::new()
try {
    $pending = $portCheck.ConnectAsync('127.0.0.1', 5173)
    if ($pending.Wait(500) -and $portCheck.Connected) {
        throw 'El puerto 5173 ya está ocupado; no se iniciará otra instancia de Vite.'
    }
}
finally {
    $portCheck.Dispose()
}

$env:VITE_USE_MOCK = 'false'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8001'
Set-Location -LiteralPath $frontendRoot
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    throw 'No se encontró npm.cmd en PATH.'
}
& $npm.Source run dev -- --host 127.0.0.1
if ($LASTEXITCODE -ne 0) {
    throw "El frontend B5 terminó con código $LASTEXITCODE."
}
