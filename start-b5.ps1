$ErrorActionPreference = 'Stop'

$repoRoot = $PSScriptRoot
$backendTerminal = Join-Path $repoRoot 'backend\start_b5_backend.ps1'
$frontendTerminal = Join-Path $repoRoot 'frontend\start_b5_frontend.ps1'
$python = Join-Path $repoRoot 'backend\venv\Scripts\python.exe'
$passFile = Join-Path $env:APPDATA 'postgresql\pgpass.conf'

function Test-LocalPortOpen([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.ConnectAsync('127.0.0.1', $Port)
        return $pending.Wait(800) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'No se encontró backend\venv\Scripts\python.exe. Activa o prepara el entorno virtual del backend.'
}
if (-not (Test-Path -LiteralPath $passFile -PathType Leaf)) {
    throw 'No se encontró pgpass.conf en el perfil actual de Windows.'
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend\node_modules') -PathType Container)) {
    throw 'No se encontró frontend\node_modules. Instala las dependencias del frontend antes de iniciar.'
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'No se encontró npm.cmd en PATH.'
}
if (-not (Test-LocalPortOpen 5433)) {
    throw 'No hay un servidor accesible en 127.0.0.1:5433. No se inició ELISA.'
}
foreach ($port in @(8001, 5173)) {
    if (Test-LocalPortOpen $port) {
        throw "El puerto local $port ya está ocupado. Cierra la instancia anterior antes de iniciar otra."
    }
}

$shell = Get-Command pwsh.exe -ErrorAction SilentlyContinue
if ($shell) {
    $shellPath = $shell.Source
}
else {
    $shellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $shellPath -PathType Leaf)) {
        throw 'No se encontró pwsh.exe ni Windows PowerShell en este equipo.'
    }
}

Start-Process -FilePath $shellPath -ArgumentList @(
    '-NoExit', '-NoProfile', '-ExecutionPolicy', 'RemoteSigned',
    '-File', ('"{0}"' -f $backendTerminal)
) | Out-Null
Start-Sleep -Milliseconds 500
Start-Process -FilePath $shellPath -ArgumentList @(
    '-NoExit', '-NoProfile', '-ExecutionPolicy', 'RemoteSigned',
    '-File', ('"{0}"' -f $frontendTerminal)
) | Out-Null

Write-Host 'ELISA B5 se está iniciando en dos ventanas.' -ForegroundColor Green
Write-Host 'Backend: http://127.0.0.1:8001  |  Frontend: http://127.0.0.1:5173'
Write-Host 'El backend confirma la identidad PostgreSQL antes de abrir el puerto 8001.'
