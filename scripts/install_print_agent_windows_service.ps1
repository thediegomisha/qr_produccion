$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Import-EnvFile($path) {
    if (-not (Test-Path $path)) { return }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) { return }
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"')
        if ($key) { $env:$key = $val }
    }
}

Import-EnvFile (Join-Path $root ".env")
Import-EnvFile (Join-Path $root "backend/.env")

$agentToken = $env:AGENT_TOKEN
if (-not $agentToken) { $agentToken = $env:PRINT_AGENT_TOKEN }
if (-not $agentToken) { $agentToken = "change-me" }

$agentId = $env:AGENT_ID
if (-not $agentId) { $agentId = "agent-001" }

$agentHost = $env:AGENT_HOST
if (-not $agentHost) { $agentHost = "0.0.0.0" }

$agentPort = $env:AGENT_PORT
if (-not $agentPort) { $agentPort = "5000" }

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$env:PYTHONPATH = (Join-Path $root "backend")

$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "NSSM no encontrado. Instala NSSM y vuelve a ejecutar."
    Write-Host "Descarga: https://nssm.cc/download"
    exit 1
}

$serviceName = "qr-print-agent"
$args = "-m uvicorn app.print_agent.agent_app:app --host $agentHost --port $agentPort"

Write-Host "Instalando servicio $serviceName"

& nssm install $serviceName $python $args
& nssm set $serviceName AppDirectory $root
& nssm set $serviceName AppEnvironmentExtra "AGENT_TOKEN=$agentToken" "AGENT_ID=$agentId" "PYTHONPATH=$env:PYTHONPATH" "AGENT_HOST=$agentHost" "AGENT_PORT=$agentPort"
& nssm set $serviceName Start SERVICE_AUTO_START

& nssm start $serviceName

Write-Host "Servicio instalado y iniciado."
Write-Host "Print Agent -> http://$agentHost`:$agentPort"
